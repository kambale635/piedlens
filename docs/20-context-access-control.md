# Bounded Context : Access Control (rôles & permissions, niveau SaaS pro)

## Rôle
Gérer QUI peut faire QUOI, sur QUELLES données, sans jamais coder un `if role == "admin"` où que ce soit dans le système. C'est un moteur de permissions **configurable en base**, sur le même principe que le Rules Engine (`08-context-rules-engine.md`) : ajouter un rôle, une permission, ou changer qui a accès à quoi = une opération d'administration, jamais un déploiement de code.

## Pourquoi PBAC (Policy-Based) plutôt que RBAC codé en dur

Le RBAC classique codé en dur (`if user.role == "admin": allow_all()`) est rigide : chaque nouveau cas (un rôle "support" qui peut voir mais pas modifier, un rôle "agence" qui gère plusieurs merchants) oblige à retoucher le code. On modélise donc :

- Des **Permissions** atomiques et nommées (`order.read`, `order.update_status`, `contact.export`, `merchant.delete_data`, `rule_config.edit`, ...)
- Des **Roles** qui sont des ensembles de permissions, entièrement configurables (pas de rôle codé en dur, même "admin" est un `Role` en base comme les autres — seul son contenu de permissions le rend spécial)
- Des **RoleAssignments** qui lient un utilisateur à un ou plusieurs rôles, avec une **portée** (scope) : global, ou restreint à un `merchantId` précis (essentiel pour le plan Agency, où un utilisateur agence gère plusieurs merchants sans que ça devienne un rôle "agence" codé spécifiquement)

## Modèle de domaine

### Permission [VO]
Chaîne structurée `resource.action` (ex : `order.update_status`, `contact.export`, `backup.restore`). Catalogue exhaustif maintenu dans `24-permissions-catalog.md` (à créer au fil du développement, généré automatiquement à partir des Use Cases protégés — voir §5).

### Role [AR]
| Attribut | Type |
|---|---|
| id | RoleId [VO] |
| name | string (unique) |
| permissions | Set\<Permission [VO]\> |
| isSystemRole | boolean (les rôles système — `Owner`, `Admin` — ne peuvent pas être supprimés, mais leurs permissions restent éditables) |

### RoleAssignment [AR]
| Attribut | Type |
|---|---|
| id | RoleAssignmentId [VO] |
| userId | UserId [VO] |
| roleId | RoleId [VO] |
| scope | AccessScope [VO] (Global \| Merchant(merchantId)) |
| grantedAt | DateTime |
| grantedBy | UserId [VO] (traçabilité obligatoire — qui a donné ce droit à qui) |

### AccessScope [VO]
Empêche un utilisateur d'un merchant A d'agir sur les données du merchant B, même s'il a un rôle avec les bonnes permissions — le scope est vérifié **en plus** de la permission, jamais l'un sans l'autre.

## Interface (port) — LE point d'entrée unique pour toute vérification d'accès

```
interface IPermissionChecker {
  can(userId: UserId, permission: Permission, scope: AccessScope): boolean
}
```

**Règle absolue** : dans tout le reste du système, aucune vérification d'accès n'est faite autrement que via un appel à `IPermissionChecker.can(...)`. Jamais de comparaison de rôle en dur dans un contrôleur, un Use Case, ou ailleurs. C'est l'équivalent, pour la sécurité, de ce que `IRuleEvaluator` est pour la détection métier.

## Use Cases

### `CreateRoleUseCase`
- **Entrée** : `{ name: string, permissions: string[] }`
- **Sortie** : `{ roleId: uuid }`
- **Préconditions** : chaque permission doit exister dans le catalogue (`24-permissions-catalog.md`) — refus si permission inconnue, pour éviter les fautes de frappe silencieuses
- **Erreurs** : `400 UNKNOWN_PERMISSION`, `409 ROLE_NAME_ALREADY_EXISTS`

### `UpdateRolePermissionsUseCase`
- **Entrée** : `{ roleId: uuid, permissions: string[] }`
- **Sortie** : `{ roleId: uuid, permissions: string[] }`
- **Préconditions** : si `isSystemRole = true`, la modification reste autorisée (l'admin peut ajuster même les rôles système), mais l'événement publié est marqué comme sensible (voir audit, §6)
- **Événements publiés** : `RolePermissionsChanged`

### `AssignRoleToUserUseCase`
- **Entrée** : `{ userId: uuid, roleId: uuid, scope: "global"|{merchantId: uuid}, grantedBy: uuid }`
- **Sortie** : `{ roleAssignmentId: uuid }`
- **Préconditions** : `grantedBy` doit lui-même posséder la permission `role.assign` sur ce scope (pas d'auto-élévation de privilèges — un utilisateur ne peut jamais s'attribuer un rôle plus puissant que celui qu'il peut déjà accorder)
- **Erreurs** : `403 INSUFFICIENT_PRIVILEGE_TO_GRANT`
- **Événements publiés** : `RoleAssigned`

### `RevokeRoleFromUserUseCase`
- **Entrée** : `{ roleAssignmentId: uuid, revokedBy: uuid }`
- **Sortie** : `{ revokedAt: datetime }`
- **Événements publiés** : `RoleRevoked`

### `CheckPermissionUseCase` (interne, appelé par le middleware — voir `21-middleware-layer.md`)
- **Entrée** : `{ userId: uuid, permission: string, scope: "global"|{merchantId: uuid} }`
- **Sortie** : `{ allowed: boolean }`
- **Note technique** : résultat mis en cache Redis très court (quelques secondes, TTL agressif), invalidé immédiatement sur `RolePermissionsChanged`/`RoleAssigned`/`RoleRevoked` — la sécurité ne tolère pas un cache périmé trop longtemps.

## Rôles système fournis par défaut (créés au seed initial, mais éditables ensuite)

| Rôle | Permissions par défaut |
|---|---|
| `Owner` | toutes les permissions, scope global — le créateur du compte merchant |
| `Admin` (plateforme, pas merchant) | toutes les permissions, tous scopes — équipe interne uniquement |
| `Staff` (merchant) | lecture/écriture sur order, contact, backup de SON merchant, pas de suppression de compte |
| `ReadOnlyAuditor` | lecture seule sur tout, pour un futur cas d'usage support client |

**Important** : ce tableau n'est PAS codé en dur dans le système — c'est le contenu du script de seed initial (`seed_default_roles.py`), modifiable ensuite depuis l'interface admin sans toucher au code, exactement l'exigence exprimée.

## Invariants (à ajouter dans `16-business-invariants-and-rules.md`, voir mise à jour)

- **INV-AC-01** : aucune vérification d'accès dans le code applicatif/présentation autrement que via `IPermissionChecker.can()` — zéro comparaison de rôle en dur.
- **INV-AC-02** : un utilisateur ne peut jamais accorder (`AssignRoleToUserUseCase`) un rôle dont les permissions dépassent celles qu'il possède lui-même sur le même scope (anti auto-élévation).
- **INV-AC-03** : toute action sur les données d'un merchant vérifie le scope (`AccessScope`) EN PLUS de la permission — un `Staff` du merchant A ne peut jamais agir sur le merchant B même avec la bonne permission nommée.
- **INV-AC-04** : toute création/modification/révocation de rôle ou d'assignation est tracée (`grantedBy`, horodatage) — jamais d'action silencieuse sur les droits d'accès.
- **INV-AC-05** : le cache de vérification de permission a un TTL cours (secondes) et est invalidé immédiatement sur tout changement de rôle/assignation — jamais de fenêtre de tolérance longue sur une permission révoquée.

## Tests attendus

- Test d'anti-élévation de privilège (`INV-AC-02`)
- Test d'isolation de scope (`INV-AC-03`) — un Staff du merchant A ne peut jamais lire une commande du merchant B
- Test d'invalidation de cache immédiate après révocation
- Test de non-régression : chaque nouvelle permission ajoutée au catalogue doit avoir au moins un test qui vérifie qu'elle bloque bien l'accès sans elle

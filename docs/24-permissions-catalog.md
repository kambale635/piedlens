# Catalogue des permissions

Catalogue extrait des vues enregistrées dans le resolver Django, via leur attribut `required_permission` posé par `@requires_permission`.

| Permission | Contexte | Routes protégées |
|---|---|---|
| `role.create` | Access Control | `POST /api/v1/roles` |
| `role.update` | Access Control | `PUT /api/v1/roles/{role_id}/permissions` |
| `role.assign` | Access Control | `POST /api/v1/role-assignments` |
| `role.revoke` | Access Control | `DELETE /api/v1/role-assignments/{role_assignment_id}` |

Les routes publiques Identity et `POST /api/v1/merchants` ont une politique publique explicite; elles n'ajoutent pas de permission. Aucun Use Case CRM ou Order Detection n'a de route déclarée dans `07-api-contracts.md`, donc aucun droit de ces contextes n'est inventé ici. Toute route non marquée `@requires_permission` ou `@public_route` est refusée par défaut.

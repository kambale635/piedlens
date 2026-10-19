# Invariants métier & Règles — Document consolidé (source unique de vérité)

> Ce fichier rassemble en un seul endroit **tous** les invariants et règles métier disséminés dans les fichiers de contexte, pour qu'aucune règle ne soit jamais oubliée ou contredite entre deux modules. En cas de divergence apparente entre ce fichier et un fichier de contexte, **ce fichier fait foi** — les fichiers de contexte doivent être corrigés pour s'aligner.

## 1. Invariants — Identity & Access

- **INV-ID-01** : Un `Merchant` ne peut pas dépasser le nombre de `PlatformConnection` actives autorisées par son plan.
  - Starter = 1, Pro = 3, Agency = illimité
- **INV-ID-02** : `phoneNumber` est unique globalement (contrainte d'unicité en base, pas seulement applicative)
- **INV-ID-03** : Un downgrade de plan est refusé si l'usage actuel dépasse la limite du plan cible (ex : 3 connexions actives, tentative de passage à Starter qui n'en autorise qu'1) → `422 DOWNGRADE_EXCEEDS_CURRENT_USAGE`
- **INV-ID-04** : Le mot de passe n'est jamais stocké ni journalisé en clair ; seul un hash (hasher Django) est persisté.
- **INV-ID-05** : Une erreur de connexion ne révèle jamais si le numéro existe (même réponse `401 INVALID_CREDENTIALS`).
- **INV-ID-06** : L'appartenance d'un `User` à un `Merchant` n'existe que par `RoleAssignment` (Access Control), jamais dupliquée dans Identity.

## 2. Invariants — Platform Connectors

- **INV-PC-01** : `accessToken` n'est jamais stocké ou manipulé en clair en dehors de la couche infrastructure — le domaine ne connaît que `EncryptedToken`.
- **INV-PC-02** : Un webhook entrant sans signature valide est rejeté systématiquement (`401`), jamais traité même partiellement.
- **INV-PC-03** : Idempotence des messages — un `externalMessageId` déjà traité ne crée jamais un second `Message` (contrainte d'unicité DB sur `(platformConnectionId, externalMessageId)`).
- **INV-PC-04** : Un échec de synchronisation sur une `PlatformConnection` n'affecte jamais le traitement des autres connexions du même merchant ou d'autres merchants (isolation stricte des erreurs).

## 3. Invariants — Rules Engine

- **INV-RE-01** : Résolution de `RuleSet` par priorité stricte : règles `merchant` > règles `country` > règles `global`. Une règle plus spécifique surcharge toujours une règle plus générale du même type.
- **INV-RE-02** : `ConfidenceScore` est toujours borné [0, 100] — toute tentative de construction hors limite lève une exception à la construction du Value Object, jamais un clamp silencieux.
- **INV-RE-03** : Un ajustement de poids de règle suite à une correction manuelle (`AdjustRuleWeightFromCorrectionUseCase`) est borné à ±10 points par correction, pour éviter l'instabilité du système suite à une série de corrections contradictoires.
- **INV-RE-04** : Aucune chaîne de langue, devise, ou motif de détection n'est codée en dur dans le domaine ou l'application — toute donnée de ce type provient exclusivement de `RuleConfig` en base.

## 4. Invariants — Backup

- **INV-BK-01** : Un `BackupSnapshot` marqué `Succeeded` est immuable — jamais modifié après coup, uniquement remplacé par un nouveau snapshot.
- **INV-BK-02** : Un snapshot partiellement échoué (coupure en cours de traitement) est marqué `Failed` intégralement — jamais de snapshot partiel marqué `Succeeded`.
- **INV-BK-03** : Consentement explicite du merchant (`consentGivenAt` renseigné) obligatoire avant toute sauvegarde de données clients.
- **INV-BK-04** : `DeleteAllMerchantDataUseCase` nécessite une double confirmation (`confirmationToken`) — action irréversible, jamais déclenchable en un seul appel.

## 5. Invariants — Order Detection

- **INV-OD-01** : Machine à états stricte pour `Order.status` :
  ```
  pending_payment → paid_not_delivered → paid_and_delivered
  pending_payment → cancelled
  paid_not_delivered → cancelled
  ```
  Toute transition hors de ce graphe lève `InvalidOrderTransitionException`, levée **dans l'agrégat lui-même**, jamais dans un Use Case.
- **INV-OD-02** : Corrélation d'un nouveau signal avec une commande existante : uniquement si même `contactId` ET dans une fenêtre temporelle configurable (défaut 3 jours). Au-delà, nouvelle commande distincte, même client.
- **INV-OD-03** : Le montant retenu pour un `Order` est celui détecté dans le **dernier** message contenant un `AmountPattern` avant le signal de paiement — jamais le premier montant mentionné (cas de négociation).
- **INV-OD-04** : Détection automatique de commande uniquement si `confidenceScore >= seuil configuré` (défaut 70) → création directe d'un `Order` en `pending_payment`. En dessous du seuil, **aucun `Order` n'est créé** — un `DetectionCandidate` est créé à la place, en statut `PendingReview`. `Order` ne possède jamais d'état "incertain" dans sa propre machine à états (voir INV-OD-07).
- **INV-OD-07** : Un `DetectionCandidate` ne devient un `Order` que par promotion explicite (`ValidateOrRejectDetectionUseCase`, décision `validate`), qui crée un **nouvel** `Order` avec un `OrderId` propre — jamais de réutilisation de `DetectionCandidateId` comme `OrderId`. Un candidat `Rejected` ne crée jamais d'`Order`.
- **INV-OD-05** : Agrégation du "argent qui dort" toujours par devise homogène (`Money.add()` refuse d'additionner deux devises différentes) — jamais d'addition arithmétique nue.
- **INV-OD-06** : Pas de double planification d'un `Reminder` identique (même `orderId` + même `reminderType`) en statut `Scheduled` simultanément.

## 6. Invariants — CRM

- **INV-CRM-01** : Clé d'identité d'un `Contact` = `externalIdentifier`, jamais `displayName`. Un changement de `displayName` met à jour le contact existant, ne crée jamais de doublon.
- **INV-CRM-02** : `CRMSegment` ne stocke jamais la liste de ses membres — toujours calculée dynamiquement (`SegmentMembershipCalculator`), pour éviter la désynchronisation entre agrégats.
- **INV-CRM-03** : Fusion de contacts (`MergeContactsUseCase`) uniquement déclenchable manuellement par le merchant, jamais automatique — trace d'audit obligatoire conservée après fusion.
- **INV-CRM-04** : `totalSpent` et `orderCount` d'un `Contact` sont recalculés uniquement en réaction à `OrderStatusChanged` (statut `paid_and_delivered`), jamais modifiés directement par un autre chemin.
- **INV-CRM-05** : Définition de l'anomalie de relation. Un contact est en anomalie si (a) il a au moins `min_purchases` achats (défaut 3), (b) son inactivité en jours dépasse l'intervalle médian entre achats × `anomaly_multiplier` (défaut 2.0), et (c) son inactivité est >= `min_inactivity_days` (défaut 7). Ces trois paramètres sont configurables (défauts en configuration, surcharge par merchant), jamais codés en dur dans le domaine.
- **INV-CRM-06** : Une seule alerte `RelationshipAnomalyDetected` par période de silence d'un contact : pas de nouvelle alerte tant qu'un nouvel achat n'a pas eu lieu. L'événement passe par l'Outbox CRM, dans la même transaction que l'enregistrement de la notification émise.
- **INV-CRM-07** : Un `Contact` fusionné (`Merged`) est un tombstone : jamais supprimé, ses identifiants externes redirigent vers le contact principal (`mergedIntoContactId`). La fusion respecte INV-TR-01 en deux transactions reliées par l'événement `ContactMerged`.
- **INV-CRM-08** : Un `Contact` peut dépenser dans plusieurs devises ; ses dépenses sont stockées par devise (`spendingByCurrency`), jamais additionnées entre devises, aucune conversion implicite (cohérent avec INV-OD-05). Une règle de segment sur `totalSpent` doit préciser sa devise ; un contact sans dépense dans cette devise vaut 0 pour cette règle. Le score de fidélité n'utilise que la devise principale du merchant. Une conversion avec taux configurables est reportée en V2.

## 7. Invariants transverses (tous contextes)

- **INV-TR-01** : Aucun agrégat modifié en dehors de sa propre transaction — jamais deux Aggregate Roots modifiés dans la même opération. Communication inter-agrégats exclusivement par événements.
- **INV-TR-02** : Toute émission d'événement de domaine passe par la table `outbox_events` du contexte producteur, dans la même transaction que la modification de l'agrégat (voir `14-event-driven-architecture.md`).
- **INV-TR-03** : Tout consommateur d'événement est idempotent — vérifie `processed_events` avant traitement, sans exception.
- **INV-TR-04** : Les tables résident dans le schéma PostgreSQL `public` et leur nom commence par le préfixe de leur app Django (`<app_label>_`). Aucun modèle ne déclare de `ForeignKey`, `OneToOneField` ou `ManyToManyField` vers un autre bounded context; aucune jointure ORM ou import direct ne traverse ces frontières. Les échanges passent par des ports exposés ou des événements. Le test d'architecture vérifie ces règles. Le routage vers des schémas PostgreSQL natifs par contexte est reporté par décision réversible dans `docs/13-technology-decision-adr.md`.
- **INV-TR-05** : Tout `Money` circule toujours comme Value Object `{ amount, currency }`, jamais comme nombre nu, dans quelque contexte que ce soit.

## 8. Règles de limites par plan

Les valeurs effectives sont les entitlements du catalogue Billing; aucun contexte ne lit les tables Billing directement. Les valeurs ci-dessous sont le seed provisoire initial (`seed_billing_plans`), modifiable par `plan.manage` sans redéploiement. `-1` signifie illimité. Les prix sont des montants USD en centimes avec pays `*` comme repli, jamais convertis automatiquement; ils ne constituent pas une décision commerciale définitive.

| Plan provisoire | Pays | Période (jours) | Prix (USD, centimes) |
|---|---:|---:|---:|
| Discovery | * | — | Gratuit, aucune ligne de prix |
| Starter | * | 7 / 30 / 365 | 60 / 200 / 2000 |
| Pro | * | 7 / 30 / 365 | 150 / 500 / 5000 |
| Agency | * | 30 / 365 | 1500 / 15000 |

| Entitlement provisoire | Discovery | Starter | Pro | Agency |
|---|---:|---:|---:|---:|
| `max_connections` | 1 | 1 | 3 | -1 |
| `sync_mode` | hourly | hourly | realtime | realtime |
| `history_days` | 7 | 90 | 365 | 730 |
| `dormant_money_detail` | false | true | true | true |
| `reminder_modes` | [] | [manual_link] | [manual_link, api_send] | [manual_link, api_send] |
| `outbound_monthly_cap` | 0 | 0 | 200 | 1000 |
| `max_segments` | 0 | 3 | -1 | -1 |
| `bulk_messages` | false | false | true | true |
| `max_managed_merchants` | 0 | 0 | 0 | 20 |
| `export_enabled` | true | true | true | true |

Discovery conserve l'export des données (INV-PLAN-02). Tout refus d'entitlement est `402 PLAN_UPGRADE_REQUIRED` et inclut la clé manquante. Les prix, quotas et autres valeurs ci-dessus restent des données configurables, pas des constantes métier.

- **INV-PLAN-01** : tout contexte consommateur lit les limites d'un merchant exclusivement via `IEntitlementReader`; aucune lecture directe des tables Billing. Toute limite configurée dépassée retourne `402 PLAN_UPGRADE_REQUIRED` avec la clé d'entitlement manquante.
- **INV-PLAN-02** : l'export des données reste autorisé pour tous les plans. `export_enabled` ne peut pas être désactivé par l'administration.

## 9. Règles de sécurité et conformité (rappel consolidé)

- Chiffrement au repos de tout token d'accès plateforme (AES-256 minimum)
- Aucun contenu de message client en clair dans les logs applicatifs
- Droit à l'oubli implémenté dès le MVP, pas reporté en V2
- Consentement explicite tracé avant toute collecte/sauvegarde de données clients d'un merchant

## 10. Invariants — Access Control (rôles & permissions)

- **INV-AC-01** : aucune vérification d'accès dans le code applicatif/présentation autrement que via `IPermissionChecker.can()` — zéro comparaison de rôle en dur.
- **INV-AC-02** : un utilisateur ne peut jamais accorder (`AssignRoleToUserUseCase`) un rôle dont les permissions dépassent celles qu'il possède lui-même sur le même scope (anti auto-élévation).
- **INV-AC-03** : toute action sur les données d'un merchant vérifie le scope (`AccessScope`) EN PLUS de la permission — un `Staff` du merchant A ne peut jamais agir sur le merchant B même avec la bonne permission nommée.
- **INV-AC-04** : toute création/modification/révocation de rôle ou d'assignation est tracée (`grantedBy`, horodatage) — jamais d'action silencieuse sur les droits d'accès. Les attributions automatiques (rôle Owner à la création d'un merchant) sont tracées avec l'acteur `system`.
- **INV-AC-05** : le cache de vérification de permission a un TTL court (secondes) et est invalidé immédiatement sur tout changement de rôle/assignation.

## 11. Invariants — Gestion des erreurs

- **INV-ERR-01** : le domaine ne lève que des `DomainException`, jamais une exception technique brute (voir `22-error-handling-and-exceptions.md`).
- **INV-ERR-02** : une exception non prévue (500) ne renvoie jamais de stack trace ni de détail technique au client — uniquement `errorCode` et `correlationId`.
- **INV-ERR-03** : chaque `DomainException` cite l'identifiant `INV-XX-NN` de l'invariant qu'elle protège dans son docstring.

## 12. Invariants — Suppression et conservation des données merchant

- **INV-BK-05** : la demande de suppression exige une réauthentification par le mot de passe de l'utilisateur authentifié. Le jeton de confirmation est imprévisible, lié au merchant, valable 15 minutes et à usage unique; seul son hash est persisté et le jeton brut n'est jamais journalisé. La consommation est atomique avec le début effectif de la suppression. Jeton invalide, expiré ou consommé : `403 INVALID_CONFIRMATION_TOKEN`.
- **INV-BK-06** : `MerchantDataDeleted` ne permet jamais à un contexte d'effacer les tables d'un autre contexte. Chaque contexte purge uniquement ses propres données, de façon idempotente (INV-TR-03), puis publie `MerchantDataPurged { context, merchantId }` via son Outbox après achèvement local.
- **INV-ID-07** : la purge Identity supprime le `Merchant`, mais conserve tout `User`; un utilisateur peut être associé à d'autres merchants via ses `RoleAssignments`.
- **INV-AC-06** : la purge Access Control supprime uniquement les `RoleAssignments` scopés au merchant supprimé. L'audit est conservé et ne contient que les identifiants nécessaires, jamais le contenu des messages.
- **INV-PC-05** : la purge Platform Connectors détruit les tokens de connexion et supprime connexions et messages locaux du merchant; une reprise ne peut rétablir ni republier de secret supprimé.
- **INV-RE-05** : la purge Rules Engine supprime uniquement les `RuleSets` de scope merchant; les configurations globales et pays restent intactes.
- **INV-OD-08** : la purge Order Detection supprime les `Orders`, `Reminders`, `DetectionCandidates` et redirections `ContactReferenceRedirect` locaux du merchant, sans modifier de données CRM ou d'un autre contexte.
- **INV-CRM-09** : la purge CRM supprime les `Contacts` (historique d'achats inclus), segments, notifications, campagnes et journaux de destinataires locaux du merchant.
- **INV-CRM-10** : le texte des campagnes CRM persistées est chiffré par une clé applicative versionnée; seul le worker de livraison le déchiffre, et le plaintext n'est jamais journalisé.
- **INV-TR-06** : chaque purge respecte INV-TR-01 : au plus un Aggregate Root est modifié par transaction. Un marqueur de traitement local rend la cascade reprenable; l'événement de confirmation est Outbox-transactionnel et émis une seule fois par contexte.

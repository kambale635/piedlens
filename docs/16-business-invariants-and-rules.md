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
- **INV-TR-04** : Aucune requête ORM ne joint directement deux schémas de contextes différents, même si techniquement possible dans une base PostgreSQL unique.
- **INV-TR-05** : Tout `Money` circule toujours comme Value Object `{ amount, currency }`, jamais comme nombre nu, dans quelque contexte que ce soit.

## 8. Règles de limites par plan (référence unique, ne pas dupliquer ailleurs avec des valeurs différentes)

| Règle | Starter | Pro | Agency |
|---|---|---|---|
| Connexions plateforme max | 1 | 3 | illimité |
| Fréquence de synchronisation | toutes les heures | temps réel (webhook) | temps réel (webhook) |
| Relances automatiques | proposition manuelle uniquement | envoi automatique | envoi automatique |
| Segments CRM personnalisés | 3 max | illimité | illimité |
| Multi-clients (vue agence) | non | non | oui |

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

# Modèle de Domaine (DDD)

## Convention de notation
- **[AR]** = Aggregate Root (racine d'agrégat — seul point d'entrée pour modifier l'agrégat depuis l'extérieur)
- **[E]** = Entity (a une identité, mais n'est jamais modifiée directement de l'extérieur de son agrégat)
- **[VO]** = Value Object (immuable, pas d'identité propre, égalité par valeur)
- **[EVT]** = Domain Event

---

## Bounded Context : Identity & Access

### Merchant [AR]
Représente le vendeur (le client payant de la plateforme).

| Attribut | Type | Règle d'invariant |
|---|---|---|
| id | MerchantId [VO] | Unique, généré (UUID) |
| name | string | Non vide |
| phoneNumber | PhoneNumber [VO] | Format E.164 validé |
| country | CountryCode [VO] | Code ISO 3166-1 alpha-2 |
| preferredLanguage | LanguageCode [VO] | Code ISO 639-1 |
| currency | CurrencyCode [VO] | Code ISO 4217 |
| subscriptionPlan | SubscriptionPlan [VO] (Starter/Pro/Agency) | — |
| createdAt | DateTime | Immuable après création |

**Invariant métier** : un Merchant ne peut pas avoir plus de connexions de plateforme que sa limite de plan (Starter = 1, Pro = 3, Agency = illimité). Cette règle vit dans le domaine, pas dans l'infrastructure.

**Événements émis** : `MerchantRegistered [EVT]`, `MerchantPlanChanged [EVT]`

---

## Bounded Context : Platform Connectors

### PlatformConnection [AR]

| Attribut | Type |
|---|---|
| id | PlatformConnectionId [VO] |
| merchantId | MerchantId [VO] (référence, pas d'objet complet — respect des frontières d'agrégat) |
| platformType | PlatformType [VO] (enum extensible : WhatsApp, Instagram, Facebook, futur...) |
| externalAccountId | string |
| accessToken | EncryptedToken [VO] |
| connectionStatus | ConnectionStatus [VO] (Active/Expired/Revoked) |
| lastSyncedAt | DateTime? |

**Invariant** : un `accessToken` n'est **jamais** exposé en clair hors de l'agrégat — seule une méthode `decrypt(secretKey)` interne à l'infrastructure y accède, jamais le domaine directement (le domaine manipule `EncryptedToken`, point.)

**Événements émis** : `PlatformConnected [EVT]`, `PlatformConnectionExpired [EVT]`, `MessageReceived [EVT]` (déclencheur principal de tout le système)

---

## Bounded Context : Rules Engine (shared kernel)

### RuleSet [AR]
Ensemble de règles pour un scope donné (global, pays, ou merchant spécifique).

| Attribut | Type |
|---|---|
| id | RuleSetId [VO] |
| scope | RuleScope [VO] (Global / Country(code) / Merchant(id)) |
| rules | List\<Rule [E]\> |

### Rule [E] (entité, vit dans l'agrégat RuleSet)
| Attribut | Type |
|---|---|
| id | RuleId [VO] |
| type | RuleType [VO] (KeywordMatch / AmountPattern / PaymentProofSignal / CurrencyFormat) |
| language | LanguageCode [VO] |
| pattern | RulePattern [VO] (contient le motif — mot-clé, regex, etc.) |
| weight | ConfidenceWeight [VO] (0-100, contribue au score de confiance) |
| isActive | boolean |

### IRuleEvaluator (port, interface du domaine)
```
interface IRuleEvaluator {
  evaluate(message: MessageContent, ruleSet: RuleSet): EvaluationResult
}
```
**Principe SOLID appliqué ici : Open/Closed.** Ajouter un nouveau `RuleType` (ex: détection d'image de reçu par OCR) ne modifie pas `IRuleEvaluator` ni le code appelant — on ajoute une nouvelle stratégie d'évaluation qui implémente l'interface existante (voir `03-solid-principles.md`, section OCP).

### EvaluationResult [VO]
| Attribut | Type |
|---|---|
| confidenceScore | number (0-100) |
| matchedRules | List\<RuleId\> |
| extractedData | Map (ex : montant détecté, devise détectée) |

---

## Bounded Context : Backup

### BackupSnapshot [AR]

| Attribut | Type |
|---|---|
| id | SnapshotId [VO] |
| merchantId | MerchantId [VO] |
| platformConnectionId | PlatformConnectionId [VO] |
| snapshotDate | DateTime |
| status | SnapshotStatus [VO] (InProgress/Succeeded/Failed) |
| dataIntegrityHash | Hash [VO] |
| storageReference | StorageReference [VO] (pointeur vers l'infra, jamais l'infra elle-même) |

**Invariant** : un snapshot `Succeeded` est immuable — on ne le modifie jamais, on en crée un nouveau. (Value Object-like behavior sur l'agrégat entier une fois clos.)

**Événements émis** : `BackupCompleted [EVT]`, `BackupFailed [EVT]` (doit déclencher une alerte au merchant)

---

## Bounded Context : Order Detection ("argent qui dort")

### DetectionCandidate [AR]
Représente un signal détecté par le Rules Engine dont le score de confiance est **sous le seuil** requis pour créer automatiquement un `Order`. Séparé de `Order` intentionnellement : un `Order` en dessous du seuil n'est pas une commande incertaine, ce n'est pas encore une commande du tout — lui donner un statut au sein de la machine à états d'`Order` polluerait cet agrégat avec un état qui n'a pas les mêmes invariants (pas de montant confirmé, pas de relance possible, pas d'agrégation dans le dashboard "argent qui dort").

| Attribut | Type |
|---|---|
| id | DetectionCandidateId [VO] |
| merchantId | MerchantId [VO] |
| contactId | ContactId [VO] |
| evaluationResult | EvaluationResult [VO] (score, données extraites — voir `08-context-rules-engine.md`) |
| sourceMessageIds | List\<MessageId\> |
| status | CandidateStatus [VO] (PendingReview / Promoted / Rejected) |
| createdAt | DateTime |
| reviewedAt | DateTime? |
| reviewedBy | MerchantId? (le merchant qui valide/rejette) |

**Invariant** : un `DetectionCandidate` `Promoted` déclenche la création d'un `Order` distinct (nouvel identifiant `OrderId`, pas de réutilisation de l'id du candidat) — le candidat garde une référence vers l'`Order` créé (`promotedToOrderId`) pour la traçabilité, mais reste lui-même immuable une fois `Promoted` ou `Rejected`.

**Événements émis** : `DetectionCandidateCreated [EVT]`, `DetectionCandidatePromoted [EVT]`, `DetectionCandidateRejected [EVT]`

### Order [AR]

| Attribut | Type |
|---|---|
| id | OrderId [VO] |
| merchantId | MerchantId [VO] |
| contactId | ContactId [VO] (référence vers le contexte CRM, pas l'objet complet) |
| detectedAmount | Money [VO] (montant + devise, jamais un nombre nu) |
| status | OrderStatus [VO] (PendingPayment/PaidNotDelivered/PaidAndDelivered/Cancelled) |
| confidenceScore | ConfidenceScore [VO] (0-100) |
| sourceMessageIds | List\<MessageId\> |
| createdAt | DateTime |
| lastStatusChangeAt | DateTime |

**Invariant métier critique** : une transition de statut ne peut se faire que dans un ordre valide (machine à états) :
```
PendingPayment → PaidNotDelivered → PaidAndDelivered
PendingPayment → Cancelled
PaidNotDelivered → Cancelled (cas remboursement)
```
Toute tentative de transition invalide (ex: `PaidAndDelivered → PendingPayment`) doit lever une exception de domaine `InvalidOrderTransitionException`. **Cette règle vit dans la méthode `Order.changeStatus()`, jamais dans un Use Case ou un contrôleur.**

**Événements émis** : `OrderDetected [EVT]`, `PaymentDetected [EVT]`, `OrderStatusChanged [EVT]`

### Reminder [E] (entité enfant de Order, ou AR séparé selon volumétrie — recommandé : AR séparé pour scalabilité)

| Attribut | Type |
|---|---|
| id | ReminderId [VO] |
| orderId | OrderId [VO] |
| type | ReminderType [VO] |
| status | ReminderStatus [VO] (Scheduled/Sent/Processed) |
| scheduledFor | DateTime |

---

## Bounded Context : CRM

### Contact [AR]

| Attribut | Type |
|---|---|
| id | ContactId [VO] |
| merchantId | MerchantId [VO] |
| platformConnectionId | PlatformConnectionId [VO] |
| externalIdentifier | string (identifiant technique stable — JAMAIS le nom affiché, voir cas limite ci-dessous) |
| displayName | string (peut changer, non fiable comme identifiant) |
| totalSpent | Money [VO] (recalculé, jamais stocké de façon incohérente — recalcul via domain service) |
| orderCount | number |
| purchaseHistory | `PurchaseHistoryEntry[]` (orderId + date du statut `paid_and_delivered`, alimenté par le CRM) |
| lastInteractionAt | DateTime |
| loyaltyScore | LoyaltyScore [VO] (0-100, calculé par un Domain Service dédié) |
| tags | Set\<Tag [VO]\> |

**Invariant** : `externalIdentifier` est la clé d'unicité réelle, pas `displayName`. Un changement de `displayName` déclenche une mise à jour, jamais la création d'un nouveau Contact (cas limite documenté dans `12-context-crm.md`).

`purchaseHistory` est un historique CRM alimenté uniquement par les événements `OrderStatusChanged` au statut `paid_and_delivered`. La date retenue est `updatedAt` de l'événement; CRM ne lit aucune table du contexte Order Detection (INV-TR-04).

### CRMSegment [AR]

| Attribut | Type |
|---|---|
| id | SegmentId [VO] |
| merchantId | MerchantId [VO] |
| name | string |
| definitionRule | SegmentRule [VO] (règle déclarative, ex: `totalSpent > 50000 FCFA`) |

**Principe important** : `CRMSegment` ne stocke **pas** la liste des contacts membres — elle est calculée dynamiquement à la demande via un Domain Service (`SegmentMembershipCalculator`), pour éviter toute désynchronisation entre les deux agrégats `Contact` et `CRMSegment` (frontière d'agrégat stricte, cf. règle DDD "un seul agrégat modifié par transaction").

---

## Value Objects transverses (utilisés dans plusieurs contextes)

- **Money [VO]** : `{ amount: number, currency: CurrencyCode }` — toute arithmétique passe par des méthodes du VO (`add`, `subtract`), jamais d'opération arithmétique nue ailleurs dans le code.
- **PhoneNumber [VO]**, **CountryCode [VO]**, **LanguageCode [VO]**, **CurrencyCode [VO]** : validés à la construction, immuables, lèvent une exception si format invalide.
- **ConfidenceScore [VO]** : borné 0-100, refuse toute valeur hors limite à la construction.

## Domain Services (logique qui n'appartient à aucune entité seule)

- `OrderDetectionService` : orchestre `IRuleEvaluator` + création d'un `Order` à partir d'un `MessageReceived`.
- `LoyaltyScoreCalculator` : calcule `loyaltyScore` à partir de l'historique de commandes d'un `Contact`.
- `SegmentMembershipCalculator` : évalue dynamiquement quels `Contact` appartiennent à un `CRMSegment`.

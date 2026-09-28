# Catalogue complet des Use Cases — contrats de paramètres

> Chaque Use Case listé ici suit le même gabarit qu'un contrat d'API senior : nom, contexte, déclencheur, entrée typée, sortie typée, préconditions, postconditions, erreurs possibles, événements publiés. Rien n'est laissé implicite — c'est ce catalogue que Copilot doit implémenter fichier par fichier, un Use Case = une classe = un fichier.

---

## Contexte : Identity & Access

### `RegisterMerchantUseCase`
- **Déclencheur** : inscription depuis l'app
- **Entrée** : `{ name: string, phoneNumber: string, country: string(ISO 3166-1), preferredLanguage: string(ISO 639-1), currency: string(ISO 4217), password: string }`
- **Sortie** : `{ merchantId: uuid, subscriptionPlan: "starter" }`
- **Préconditions** : `phoneNumber` non déjà enregistré
- **Postconditions** : `Merchant` créé en statut actif, plan `Starter` par défaut
- **Erreurs** : `409 PHONE_ALREADY_REGISTERED`, `400 INVALID_PHONE_FORMAT`
- **Événements publiés** : `MerchantRegistered`

### `ChangeSubscriptionPlanUseCase`
- **Entrée** : `{ merchantId: uuid, newPlan: "starter"|"pro"|"agency" }`
- **Sortie** : `{ merchantId: uuid, subscriptionPlan: string, effectiveAt: datetime }`
- **Préconditions** : paiement confirmé côté fournisseur de paiement (hors scope de ce Use Case, appelé après confirmation webhook de paiement)
- **Erreurs** : `422 DOWNGRADE_EXCEEDS_CURRENT_USAGE` (ex: merchant a 3 connexions actives, tente de repasser Starter qui n'en autorise qu'1)
- **Événements publiés** : `MerchantPlanChanged`

---

## Contexte : Platform Connectors

### `ConnectPlatformUseCase`
- **Entrée** : `{ merchantId: uuid, platformType: "whatsapp"|"instagram"|"facebook", oauthCode: string }`
- **Sortie** : `{ platformConnectionId: uuid, connectionStatus: "active" }`
- **Préconditions** : `merchantId` n'a pas atteint la limite de connexions de son plan (voir `16-business-invariants-and-rules.md` §Plan Limits)
- **Postconditions** : `accessToken` échangé, chiffré, persisté
- **Erreurs** : `422 PLAN_CONNECTION_LIMIT_REACHED`, `400 INVALID_OAUTH_CODE`, `503 PLATFORM_API_UNAVAILABLE`
- **Événements publiés** : `PlatformConnected`

### `SyncMessagesUseCase`
- **Déclencheur** : job planifié (fréquence selon plan, voir invariants)
- **Entrée** : `{ platformConnectionId: uuid, since: datetime }`
- **Sortie** : `{ newMessagesCount: number, lastSyncedAt: datetime }`
- **Erreurs (par connexion, isolées, ne bloquent pas les autres)** : `503 PLATFORM_API_UNAVAILABLE`, `401 TOKEN_EXPIRED` → déclenche `RefreshTokensUseCase`
- **Événements publiés** : `MessageReceived` (un par nouveau message, via Outbox — voir `14-event-driven-architecture.md`)

### `HandleIncomingWebhookUseCase`
- **Entrée** : payload brut spécifique plateforme + en-têtes de signature
- **Sortie** : `200 OK` (accusé de réception obligatoire rapide, traitement métier différé si lourd)
- **Préconditions** : signature valide (`X-Hub-Signature-256` ou équivalent selon plateforme)
- **Erreurs** : `401 INVALID_WEBHOOK_SIGNATURE`
- **Événements publiés** : `MessageReceived`

### `RefreshTokensUseCase`
- **Déclencheur** : job planifié préventif (avant expiration) ou réactif (sur `401`)
- **Entrée** : `{ platformConnectionId: uuid }`
- **Sortie** : `{ connectionStatus: "active"|"expired" }`
- **Événements publiés** : `PlatformConnectionExpired` (si le rafraîchissement échoue définitivement)

---

## Contexte : Rules Engine

### `EvaluateMessageUseCase`
- **Entrée** : `{ merchantId: uuid, messageId: uuid, textContent: string, hasMedia: boolean, conversationContext: Message[] (fenêtre récente) }`
- **Sortie** : `{ confidenceScore: number(0-100), matchedRuleIds: uuid[], extractedData: { amount?: Money, currency?: string, intent?: string } }`
- **Préconditions** : un `RuleSet` résolu (fusion global < pays < merchant)
- **Événements publiés** : `MessageEvaluated`

### `UpdateRuleSetUseCase`
- **Entrée** : `{ scope: "global"|{country: string}|{merchantId: uuid}, rules: Rule[] }`
- **Sortie** : `{ ruleSetId: uuid, version: number }`
- **Préconditions** : chaque `Rule.weight` entre 0 et 100 ; `pattern` non vide
- **Erreurs** : `400 INVALID_RULE_WEIGHT`, `400 EMPTY_PATTERN`

### `AdjustRuleWeightFromCorrectionUseCase`
- **Déclencheur** : événement `DetectionCorrectedByMerchant`
- **Entrée** : `{ merchantId: uuid, ruleId: uuid, wasCorrect: boolean }`
- **Sortie** : `{ newWeight: number }`
- **Postconditions** : ajustement borné (jamais plus de ±10 points par correction, pour éviter l'instabilité — voir invariants)

---

## Contexte : Backup

### `CreateSnapshotUseCase`
- **Déclencheur** : job planifié (fréquence selon plan)
- **Entrée** : `{ platformConnectionId: uuid }`
- **Sortie** : `{ snapshotId: uuid, status: "succeeded"|"failed", messageCount: number, mediaCount: number }`
- **Postconditions** : `dataIntegrityHash` calculé et persisté ; si `failed`, aucune donnée partielle marquée succeeded
- **Événements publiés** : `BackupCompleted` | `BackupFailed`

### `RestoreFromSnapshotUseCase`
- **Entrée** : `{ platformConnectionId: uuid, asOfDate?: datetime }` (défaut : dernier snapshot réussi)
- **Sortie** : `{ exportJobId: uuid, status: "processing" }` puis, une fois prêt : `{ downloadUrl: string, expiresAt: datetime }`
- **Erreurs** : `404 NO_SNAPSHOT_AVAILABLE`

### `CheckAccountHealthUseCase`
- **Déclencheur** : job planifié
- **Entrée** : `{ platformConnectionId: uuid }`
- **Sortie** : `{ healthStatus: "healthy"|"at_risk"|"suspended", signals: string[] }`
- **Événements publiés** : `AccountHealthAlertRaised` (si `at_risk` ou `suspended`)

### `DeleteAllMerchantDataUseCase`
- **Entrée** : `{ merchantId: uuid, confirmationToken: string }`
- **Sortie** : `{ deletedAt: datetime }`
- **Préconditions** : `confirmationToken` valide (double confirmation obligatoire — action irréversible)
- **Événements publiés** : `MerchantDataDeleted` (consommé par tous les autres contextes pour purge en cascade)

---

## Contexte : Order Detection

### `DetectOrderUseCase`
- **Déclencheur** : événement `MessageEvaluated` avec signal d'intention d'achat
- **Entrée** : `{ merchantId: uuid, contactId: uuid, evaluationResult: EvaluationResult, sourceMessageId: uuid }`
- **Sortie (score ≥ seuil)** : `{ outcome: "order_created", orderId: uuid, status: "pending_payment" }`
- **Sortie (score < seuil)** : `{ outcome: "candidate_created", candidateId: uuid, status: "pending_review" }`
- **Préconditions** : voir INV-OD-04, INV-OD-07 (`16-business-invariants-and-rules.md`) — aucun `Order` n'est jamais créé sous le seuil, un `DetectionCandidate` l'est à la place
- **Postconditions** : si `order_created`, corrélation avec commande existante du même contact si dans la fenêtre temporelle (voir INV-OD-02)
- **Événements publiés** : `OrderDetected` (cas `order_created`) ou `DetectionCandidateCreated` (cas `candidate_created`)

### `UpdateOrderStatusUseCase`
- **Entrée** : `{ orderId: uuid, newStatus: "paid_not_delivered"|"paid_and_delivered"|"cancelled", triggeredBy: "system"|"merchant" }`
- **Sortie** : `{ orderId: uuid, status: string, updatedAt: datetime }`
- **Préconditions** : transition valide selon la machine à états (voir `02-domain-model.md` et invariants)
- **Erreurs** : `409 INVALID_ORDER_TRANSITION`
- **Événements publiés** : `OrderStatusChanged`

### `GetDormantMoneyDashboardUseCase`
- **Entrée** : `{ merchantId: uuid, olderThanHours?: number (défaut 24) }`
- **Sortie** : `{ totalDormantAmount: Money, orders: OrderSummary[] }`

### `ScheduleReminderUseCase`
- **Entrée** : `{ orderId: uuid, reminderType: "payment_pending"|"delivery_pending", customMessage?: string }`
- **Sortie** : `{ reminderId: uuid, scheduledFor: datetime }`
- **Préconditions** : pas de `Reminder` déjà `Scheduled` identique pour cet `orderId` et ce `reminderType` (anti-doublon)

### `SendScheduledRemindersUseCase`
- **Déclencheur** : job planifié
- **Entrée** : aucun paramètre externe (lit les `Reminder` dus)
- **Sortie** : `{ sentCount: number, failedCount: number }`
- **Événements publiés** : `ReminderSent` (par relance)

### `ValidateOrRejectDetectionUseCase`
- **Entrée** : `{ candidateId: uuid, decision: "validate"|"reject", merchantId: uuid }`
- **Sortie (validate)** : `{ candidateId: uuid, status: "promoted", createdOrderId: uuid }` — un nouvel `Order` est créé en `pending_payment` (voir INV-OD-07), distinct de `candidateId`
- **Sortie (reject)** : `{ candidateId: uuid, status: "rejected" }` — aucun `Order` créé
- **Préconditions** : `DetectionCandidate.status == PendingReview` (un candidat déjà `Promoted`/`Rejected` est immuable — erreur `409 CANDIDATE_ALREADY_REVIEWED`)
- **Événements publiés** : `DetectionCandidatePromoted` + `OrderDetected` (cas validate), ou `DetectionCandidateRejected` (cas reject) ; dans les deux cas, `DetectionCorrectedByMerchant` est aussi publié pour alimenter l'ajustement du Rules Engine (voir `08-context-rules-engine.md`)

### `ListPendingDetectionCandidatesUseCase`
- **Entrée** : `{ merchantId: uuid, page?: number, pageSize?: number }`
- **Sortie** : `{ candidates: DetectionCandidateSummary[], totalCount: number }`

---

### `ReassignContactReferencesFromContactMergedUseCase` (consumer Order Detection)
- **Déclencheur** : événement `ContactMerged` produit par CRM.
- **Entrée** : enveloppe `{ eventId, payload: { merchantId, primaryContactId, mergedContactId, snapshot } }`; Order Detection n'utilise que les IDs et ignore le snapshot CRM.
- **Sortie** : `{ reassignedOrderCount: number, reassignedCandidateCount: number }` après traitement complet.
- **Traitement transactionnel** : rechercher uniquement dans les repositories Order Detection; réattribuer chaque `Order.contactId` puis chaque `DetectionCandidate.contactId` au principal, une racine par transaction. Pas de transaction englobant plusieurs agrégats (INV-TR-01).
- **Idempotence/reprise** : chaque réattribution est idempotente et peut être rejouée après crash; marqueur de complétion `(eventId, order-detection-contact-merge-consumer)` inscrit après traitement de toutes les racines (INV-TR-03).
- **Événements publiés** : aucun événement métier requis.

## Contexte : CRM

### `UpdateContactFromMessageUseCase`
- **Déclencheur** : événement `MessageReceived`
- **Entrée** : `{ merchantId: uuid, platformConnectionId: uuid, externalIdentifier: string, displayName: string, timestamp: datetime }`
- **Sortie** : `{ contactId: uuid, isNewContact: boolean }`
- **Postconditions** : jamais de doublon créé si `externalIdentifier` déjà connu, même si `displayName` a changé

### `UpdateContactFromOrderUseCase`
- **Déclencheur** : événement `OrderStatusChanged` (statut = `paid_and_delivered`)
- **Entrée** : enveloppe `{ eventId: uuid, payload: { contactId: uuid, orderId: uuid, status: string, orderAmount: Money, updatedAt: datetime } }`
- **Sortie** : `{ contactId: uuid, totalSpentByCurrency: Money[], orderCount: number, loyaltyScore: number }`
- **Historique** : pour `paid_and_delivered`, ajoute `{ orderId, purchasedAt: updatedAt }` au `purchaseHistory` CRM du Contact; n'interroge jamais les tables Order Detection (INV-TR-04)
- **Idempotence** : déduplique `(eventId, crm-order-consumer)` dans la même transaction que Contact (INV-TR-03); un `orderId` déjà présent ne modifie pas deux fois les agrégats

### `CreateSegmentUseCase`
- **Entrée** : `{ merchantId: uuid, name: string, definitionRule: { field: string, operator: ">"|"<"|"="|"contains", value: any } }`
- **Sortie** : `{ segmentId: uuid }`
- **Erreurs** : `400 UNKNOWN_FIELD`, `400 UNSUPPORTED_OPERATOR`

### `GetSegmentMembersUseCase`
- **Entrée** : `{ segmentId: uuid, page?: number, pageSize?: number }`
- **Sortie** : `{ contacts: ContactSummary[], totalCount: number }`
- **Note technique** : résultat mis en cache Redis (TTL court, voir `04-tech-stack-infrastructure.md`)

### `SendBulkMessageUseCase`
- **Entrée** : `{ segmentId: uuid, template: string, channel: "whatsapp"|"instagram" }`
- **Sortie** : `{ bulkMessageLogId: uuid, status: "processing", recipientCount: number }`
- **Préconditions** : respect du rate limit de la plateforme cible (voir `IRateLimiter`)
- **Événements publiés** : `BulkMessageCompleted`

### `DetectRelationshipAnomalyUseCase`
- **Déclencheur** : job planifié
- **Entrée** : `{ merchantId: uuid }`
- **Sortie** : `{ anomaliesDetected: ContactAnomaly[] }` où `ContactAnomaly = { contactId: uuid, daysSinceLastPurchase: number, usualIntervalDays: number }`
- **Règle** : voir INV-CRM-05 et INV-CRM-06 (`16-business-invariants-and-rules.md`), paramètres configurables, aucune valeur codée en dur
- **Postconditions** : une notification est enregistrée par contact alerté, dans la même transaction que l'écriture Outbox (une seule alerte par période de silence)
- **Événements publiés** : `RelationshipAnomalyDetected` (par anomalie), via Outbox CRM uniquement; payload `{ merchantId, contactId, lastPurchaseOrderId, daysSinceLastPurchase, usualIntervalDays }`
- **Erreurs** : `422 INVALID_RELATIONSHIP_ANOMALY_POLICY` si les paramètres issus de la configuration sont invalides (voir `docs/22-error-handling-and-exceptions.md`)

### `MergeContactsUseCase`
- **Entrée** : `{ primaryContactId: uuid, duplicateContactId: uuid, merchantId: uuid }`
- **Sortie** : `{ primaryContactId: uuid, mergedContactId: uuid, status: "merge_in_progress" }` — la cohérence inter-contextes est éventuelle; aucun compte de commandes Order Detection n'est retourné synchroniquement.
- **Préconditions** : déclenchement manuel par le merchant (INV-CRM-03); les deux Contacts existent dans le même merchant; IDs distincts; ni le principal ni le doublon n'est déjà `Merged`.
- **Temps 1 / transaction CRM** : modifier le Contact doublon uniquement; le passer à `Merged`, définir `mergedIntoContactId`, conserver son tombstone et son audit, et ajouter `ContactMerged` à l'Outbox CRM dans la même transaction (INV-TR-01/02, INV-CRM-07).
- **Payload `ContactMerged`** : `{ eventId, merchantId, primaryContactId, mergedContactId, snapshot: { totalSpentByCurrency: Money[], orderCount, purchaseHistory: [{ orderId, purchasedAt }], tags } }`. Le snapshot est immuable et pris dans la transaction du temps 1.
- **Redirection** : dès le commit du temps 1, la résolution d'un identifiant externe lié au doublon suit `mergedIntoContactId` vers le Contact principal.
- **Temps 2 / consommateur CRM** : idempotence `processed_events`; modifier uniquement le Contact principal dans une transaction distincte, absorber les montants par devise avec `Money.add()`, unir l'historique et les tags, puis marquer l'événement traité (INV-TR-01/03).
- **Erreurs** : `404 CONTACT_NOT_FOUND` si un Contact est absent ou hors merchant; `409 CONTACTS_MUST_BE_DISTINCT` si les IDs sont identiques; `409 CONTACT_ALREADY_MERGED` si l'un des deux est déjà `Merged`.
- **Postconditions** : le doublon demeure en tombstone (INV-CRM-07); la fusion complète est éventuelle, de l'ordre de quelques secondes.

---

## Convention obligatoire de nommage des paramètres (pour cohérence inter-fichiers)

- Tout identifiant : suffixe `Id`, type `uuid` (jamais un entier auto-incrémenté exposé publiquement)
- Tout montant : toujours objet `Money { amount, currency }`, jamais un nombre nu dans un contrat d'entrée/sortie
- Toute date : ISO 8601 avec fuseau horaire explicite (`datetime`)
- Toute énumération de statut : chaîne explicite en `snake_case`, jamais un entier magique

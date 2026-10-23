# Catalogue complet des Use Cases — contrats de paramètres

> Chaque Use Case listé ici suit le même gabarit qu'un contrat d'API senior : nom, contexte, déclencheur, entrée typée, sortie typée, préconditions, postconditions, erreurs possibles, événements publiés. Rien n'est laissé implicite — c'est ce catalogue que Copilot doit implémenter fichier par fichier, un Use Case = une classe = un fichier.

---

## Contexte : Identity (détails : `25-context-identity.md`)

### `RegisterUserUseCase`
- **Mode d'entrée** : route publique
- **Entrée** : `{ phoneNumber: string, password: string, email?: string }`
- **Sortie** : `{ userId: uuid }`
- **Erreurs** : `409 PHONE_ALREADY_REGISTERED`, `400 INVALID_PHONE_FORMAT`, `400 WEAK_PASSWORD`
- **Événements publiés** : `UserRegistered`

### `AuthenticateUserUseCase`
- **Mode d'entrée** : route publique (limitée par `RateLimitMiddleware`)
- **Entrée** : `{ phoneNumber: string, password: string }`
- **Sortie** : `{ accessToken: string, refreshToken: string, expiresAt: datetime }`
- **Erreurs** : `401 INVALID_CREDENTIALS` (identique que le numéro existe ou non, INV-ID-05), `403 ACCOUNT_DISABLED`

### `RefreshAccessTokenUseCase`
- **Mode d'entrée** : route publique
- **Entrée** : `{ refreshToken: string }`
- **Sortie** : `{ accessToken: string, refreshToken: string, expiresAt: datetime }`
- **Postconditions** : rotation atomique; le refresh token presente est invalide apres succes. Un rejeu d'un refresh token deja consomme revoque toute sa famille de sessions.
- **Erreurs** : `401 INVALID_REFRESH_TOKEN`

### `LogoutUserUseCase`
- **Mode d'entrée** : route publique, le refresh token identifie la session a revoquer
- **Entrée** : `{ refreshToken: string }`
- **Sortie** : `{ loggedOut: true }` (operation idempotente, sans oracle sur l'existence de la session)
- **Postconditions** : la session et les access tokens qui lui sont lies ne sont plus acceptes.

### `RevokeAllSessionsUseCase`
- **Mode d'entrée** : route authentifiee; `actingUserId` provient exclusivement du principal authentifie
- **Entrée** : `{ actingUserId: uuid }`
- **Sortie** : `{ revokedSessionCount: number }`
- **Postconditions** : toutes les sessions de l'utilisateur sont revoquees, y compris leurs access et refresh tokens.

### `CreateMerchantUseCase`
- **Mode d'entrée** : route authentifiée (`actingUserId` vient du token, jamais du body)
- **Entrée** : `{ name: string, country: string(ISO 3166-1), preferredLanguage: string(ISO 639-1), currency: string(ISO 4217) }`
- **Sortie** : `{ merchantId: uuid, subscriptionPlan: "discovery" }`
- **Erreurs** : `400 VALIDATION_ERROR`
- **Événements publiés** : `MerchantRegistered` (consommé par Access Control, voir `AssignOwnerRoleOnMerchantRegisteredUseCase`)

### `ChangeSubscriptionPlanUseCase`
- **Entrée** : `{ merchantId: uuid, newPlan: string }` (code actif validé via `IPlanCatalogReader`; capacité via `IEntitlementReader`)
- **Sortie** : `{ merchantId: uuid, subscriptionPlan: string, effectiveAt: datetime }`
- **Préconditions** : paiement confirmé côté fournisseur de paiement (hors scope de ce Use Case, appelé après confirmation webhook de paiement)
- **Erreurs** : `422 DOWNGRADE_EXCEEDS_CURRENT_USAGE` (ex: merchant a 3 connexions actives, tente de repasser Starter qui n'en autorise qu'1)
- **Événements publiés** : `MerchantPlanChanged`

### `UpsertPlanUseCase`
- **Mode d'entrée** : `PUT /api/v1/admin/plans/{code}`, permission globale `plan.manage`
- **Entrée** : `{ code: string (path), active?: boolean, order?: integer, entitlements?: object }`
- **Sortie** : `{ code: string, is_active: boolean, display_order: integer }`
- **Postconditions** : upsert atomique du plan et des seules clés d'entitlement fournies; clés omises conservées.
- **Erreurs** : `400 INVALID_PLAN_DEFINITION`
- **Audit** : événement d'audit HTTP metadata-only par la chaîne middleware.

### `UpsertPlanPriceUseCase`
- **Mode d'entrée** : `PUT /api/v1/admin/plan-prices`, permission globale `plan.manage`
- **Entrée** : `{ planCode: string, country: ISO-3166-1 alpha-2 | "*", currency: ISO-4217, periodDays: integer, amountMinor: integer, active?: boolean }`
- **Sortie** : `{ plan_code, country, currency, period_days, amount_minor, is_active }`
- **Postconditions** : le prix explicite remplace uniquement la ligne de même plan/pays/devise/période; aucune conversion de devise.
- **Erreurs** : `404 PLAN_NOT_FOUND`, `400 INVALID_PLAN_PRICE`
- **Audit** : événement d'audit HTTP metadata-only par la chaîne middleware.

### `ListPricingUseCase`
- **Mode d'entrée** : `GET /api/v1/pricing?country={ISO-3166-1 alpha-2}`, route publique
- **Entrée** : `{ country: string }`
- **Sortie** : `{ country: string, plans: [{ code, prices: [{ country, currency, periodDays, amountMinor }], entitlements }] }`
- **Postconditions** : seuls les plans actifs sont retournés; prix pays exact d'abord, puis prix `*` pour les couples devise/période non couverts exactement; aucune conversion automatique.
- **Erreurs** : `400 VALIDATION_ERROR`

Les prix et entitlements semés pour Discovery, Starter, Pro et Agency sont des valeurs provisoires, configurables dans Billing; voir la section 8 de `16-business-invariants-and-rules.md`.

### `StartTrialUseCase`
- **Mode d'entrée** : `POST /api/v1/trials`, permission `billing.trial.start`, tenant courant
- **Entrée** : `{ merchantId: uuid (depuis tenant), cardProvided?: boolean }`
- **Sortie** : `{ merchant_id, plan_code, starts_at, ends_at }`
- **Préconditions** : policy activée, plan cible actif, carte fournie si requise, aucun essai passé pour ce merchant.
- **Postconditions** : enregistre un essai unique. À expiration, les entitlements reviennent au plan courant (Discovery par défaut); aucune donnée merchant n'est supprimée.
- **Erreurs** : `400 TRIAL_UNAVAILABLE`, `400 TRIAL_CARD_REQUIRED`
- **Référence** : INV-BILL-01.

### `ApplyCouponUseCase`
- **Mode d'entrée** : `POST /api/v1/coupons/apply`, permission `billing.coupon.apply`, tenant courant
- **Entrée** : `{ merchantId: uuid (depuis tenant), code: string }`
- **Sortie** : `{ coupon_code, discount_percent, redeemed_at, expires_at }`
- **Préconditions** : code actif, fenêtre de validité ouverte, quota global non atteint, merchant n'a pas déjà utilisé ce même coupon.
- **Postconditions** : incrémente l'usage, enregistre l'application et publie `CouponRedeemed` dans l'Outbox Billing atomiquement.
- **Erreurs** : `404 COUPON_NOT_FOUND`, `400 COUPON_NOT_VALID`, `400 COUPON_ALREADY_USED`
- **Référence** : INV-BILL-02.

### `RedeemReferralUseCase`
- **Mode d'entrée** : `POST /api/v1/referrals/redeem`, permission `billing.referral.redeem`, tenant courant
- **Entrée** : `{ referredMerchantId: uuid (depuis tenant), referrerMerchantId: uuid }`
- **Sortie** : `{ referrer_merchant_id, referred_merchant_id, reward_percent, reward_duration_days }`
- **Préconditions** : pas d'auto-parrainage, pas de parrainage préalable du filleul, limite configurable du parrain non atteinte.
- **Postconditions** : fige la récompense configurée; aucun crédit n'est accordé à cette étape.
- **Erreurs** : `400 REFERRAL_NOT_VALID`, `400 REFERRAL_ALREADY_REDEEMED`, `400 REFERRAL_LIMIT_REACHED`
- **Référence** : INV-BILL-03.

### `RecordFirstPaidPeriodUseCase`
- **Déclencheur** : confirmation interne de paiement, appelée une seule fois par la première période payée du merchant.
- **Entrée** : `{ merchantId: uuid, paidAt: datetime }`
- **Sortie** : `{ merchant_id, first_paid_period, referral_reward_granted }`
- **Postconditions** : idempotent par merchant; seul le premier paiement d'un filleul parrainé fixe le reward et publie `ReferralRewardGranted` via Outbox Billing atomiquement.
- **Référence** : INV-BILL-03, INV-TR-02/03.

### `UpsertTrialPolicyUseCase`, `UpsertReferralPolicyUseCase`, `UpsertCouponUseCase`
- **Mode d'entrée** : routes admin `PUT /api/v1/admin/trial-policy`, `PUT /api/v1/admin/referral-policy`, `PUT /api/v1/admin/coupons`, permission globale `plan.manage`.
- **Postconditions** : mettent à jour les durées, plan cible, exigence de carte, récompense, limite par parrain et définitions de coupons sans redéploiement; l'audit HTTP metadata-only est produit par les middlewares.
- **Valeurs seed provisoires** : essai Starter de 14 jours sans carte; parrainage 10% pendant 30 jours, au plus 10 filleuls par parrain. Toutes sont administrables.

### `SendBulkMessageUseCase` — extension outbound
- **Entrée** : `{ segmentId, template, channel, deliveryMode: "manual_link"|"api_send" (défaut manual_link), category: "service"|"utility"|"marketing"|"authentication", marketingConfirmed?: boolean, confirmedEstimate?: object }`
- **Préconditions** : `bulk_messages=true`; mode présent dans `reminder_modes`; pour `api_send`, quota mensuel non dépassé et tarif configuré pour le pays/catégorie/devise.
- **Postconditions** : `manual_link` retourne des liens `wa.me` pré-remplis et n'appelle aucun sender. `api_send` met la campagne en file; le quota est réservé au worker avec idempotence avant chaque appel de sender. Marketing exige la confirmation explicite de l'estimation courante.
- **Erreurs** : `402 PLAN_UPGRADE_REQUIRED`, `422 OUTBOUND_CAP_REACHED`, `400 MARKETING_CONFIRMATION_REQUIRED`, `400 OUTBOUND_RATE_NOT_CONFIGURED`, `400 MANUAL_LINK_RECIPIENT_UNAVAILABLE`.

### `EstimateOutboundCostUseCase`
- **Mode d'entrée** : `POST /api/v1/outbound/estimate`, permission `outbound.estimate`
- **Entrée** : `{ category: "service"|"utility"|"marketing"|"authentication", count?: integer }`; merchant dérivé du tenant.
- **Sortie** : `{ country, category, count, estimate: { unitAmountMinor, amountMinor, currency, numberOfMessages, chargeProcessor: "meta_direct" } }`
- **Postconditions** : lit un tarif country/category actif à la date courante; aucune conversion; aucune transaction Meta n'est débitée par Billing.
- **Erreurs** : `400 OUTBOUND_RATE_NOT_CONFIGURED`, `400 VALIDATION_ERROR`.

### `GetOutboundUsageUseCase`
- **Mode d'entrée** : `GET /api/v1/outbound/usage`, permission `outbound.usage.read`
- **Sortie** : usages API du merchant courant par catégorie pour le mois courant; les liens manuels sont exclus.

### `GenerateValueReportUseCase`
- **Mode d'entrée** : `GET /api/v1/reports/value`, permission `outbound.usage.read`
- **Entrée** : `{ merchantId: uuid }` (dérivé du tenant courant)
- **Sortie** : `{ merchantId, country, currency, month, totalAmountMinor, unpricedMessageCount, estimateIncomplete, items: [{ category, messages, priced, unitAmountMinor?, amountMinor?, currency }] }`
- **Postconditions** : agrège les usages API du mois courant et réévalue chaque catégorie au tarif actif configuré pour le pays/devise. Une catégorie sans tarif est exclue du total estimé, marquée `priced=false`, comptée dans `unpricedMessageCount` et active `estimateIncomplete=true`; elle ne peut jamais apparaître comme un coût nul silencieux.
- **Erreurs** : `400 VALIDATION_ERROR` si le merchant n'a pas de pays configuré.

### `UpsertOutboundRateUseCase`
- **Mode d'entrée** : `PUT /api/v1/admin/outbound-rates`, permission globale `plan.manage`
- **Entrée** : `{ country, category, currency, amountMinor, validFrom, validUntil?, active? }`
- **Postconditions** : administre le tarif Meta estimatif avec sa fenêtre de validité; les vrais frais Meta restent facturés directement au vendeur par Meta.
- **Valeurs par défaut** : aucun tarif n'est seedé faute de grille Meta vérifiée par pays/catégorie; l'estimation échoue clairement tant qu'une ligne valable n'est pas configurée.

**Règle de tarif manquant** : avant un envoi `api_send`, absence de tarif actif pour pays/catégorie/devise = `422 OUTBOUND_RATE_MISSING`; la réservation de quota n'est pas consommée. Pour le rapport mensuel, les catégories sans tarif sont exclues de l'estimation mais signalées par `unpricedMessageCount` et `estimateIncomplete`.

---

## Contexte : Access Control (détails : `20-context-access-control.md`)

### `CreateRoleUseCase`
- **Mode d'entrée** : route, permission `role.create`
- **Entrée** : `{ name: string, permissions: string[] }`
- **Sortie** : `{ roleId: uuid }`
- **Erreurs** : `400 UNKNOWN_PERMISSION`, `409 ROLE_NAME_ALREADY_EXISTS`

### `UpdateRolePermissionsUseCase`
- **Mode d'entrée** : route, permission `role.update`
- **Entrée** : `{ roleId: uuid, permissions: string[] }`
- **Sortie** : `{ roleId: uuid, permissions: string[] }`
- **Événements publiés** : `RolePermissionsChanged`

### `AssignRoleToUserUseCase`
- **Mode d'entrée** : route, permission `role.assign`
- **Entrée** : `{ userId: uuid, roleId: uuid, scope: "global"|{merchantId: uuid}, grantedBy: uuid }`
- **Sortie** : `{ roleAssignmentId: uuid }`
- **Erreurs** : `403 INSUFFICIENT_PRIVILEGE_TO_GRANT` (INV-AC-02)
- **Événements publiés** : `RoleAssigned`

### `RevokeRoleFromUserUseCase`
- **Mode d'entrée** : route, permission `role.revoke`
- **Entrée** : `{ roleAssignmentId: uuid, revokedBy: uuid }`
- **Sortie** : `{ revokedAt: datetime }`
- **Événements publiés** : `RoleRevoked`

### `CheckPermissionUseCase`
- **Mode d'entrée** : interne (appelé par `PermissionMiddleware`), aucune route
- **Entrée** : `{ userId: uuid, permission: string, scope: "global"|{merchantId: uuid} }`
- **Sortie** : `{ allowed: boolean }`

### `AssignOwnerRoleOnMerchantRegisteredUseCase`
- **Mode d'entrée** : consommateur de `MerchantRegistered` (idempotent, INV-TR-03)
- **Entrée** : `{ merchantId: uuid, ownerUserId: uuid }`
- **Sortie** : `{ roleAssignmentId: uuid }` (rôle `Owner`, scope `{merchantId}`, `grantedBy = system`)
- **Événements publiés** : `RoleAssigned`

---

## Contexte : Platform Connectors

### `ConnectPlatformUseCase`
- **Entrée** : `{ merchantId: uuid, platformType: "whatsapp"|"instagram"|"facebook", oauthCode: string, externalAccountId?: string, consentGiven?: boolean }`
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
- **Entrée** : payload brut spécifique plateforme + `X-Hub-Signature-256` + `X-Webhook-Timestamp`
- **Sortie** : `200 OK` (accusé de réception obligatoire rapide, traitement métier différé si lourd)
- **Préconditions** : signature valide en temps constant; horodatage dans la tolérance configurée; empreinte réclamée dans le cache Redis anti-rejeu avant parsing
- **Postconditions** : un rejeu valide est acquitté avec zéro message accepte et ne produit ni parsing ni evenement.
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
- **Entrée** : `{ eventId: uuid, merchantId: uuid, messageId: uuid, textContent: string, hasMedia: boolean, conversationContext: Message[] (fenêtre récente) }`
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
- **Entrée** : `{ eventId: uuid, merchantId: uuid, ruleId: uuid, wasCorrect: boolean }`
- **Sortie** : `{ newWeight: number }`
- **Postconditions** : ajustement borné (jamais plus de ±10 points par correction, pour éviter l'instabilité — voir invariants)

---

## Contexte : Backup

### `ListBackupsUseCase`
- **Mode d'entrée** : route protégée par `backup.read`
- **Entrée** : `{ merchantId: uuid, platformConnectionId?: uuid, page?: number, pageSize?: number }`
- **Sortie** : `{ snapshots: BackupSnapshotSummary[], totalCount: number }`

### `GetBackupExportUseCase`
- **Mode d'entrée** : route protégée par `backup.read`
- **Entrée** : `{ merchantId: uuid, exportJobId: uuid }`
- **Sortie** : `{ status: "processing"|"ready"|"failed", downloadUrl?: string, expiresAt?: datetime }`

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
- **Préconditions** : `confirmationToken` valide, non expiré et non consommé; sa consommation et la purge des données Backup sont atomiques (double confirmation obligatoire — action irréversible)
- **Erreurs** : `403 INVALID_CONFIRMATION_TOKEN` (invalide, expiré ou déjà utilisé)
- **Événements publiés** : `MerchantDataDeleted` (consommé par tous les autres contextes pour purge en cascade)

### `RequestMerchantDeletionUseCase`
- **Mode d'entrée** : route authentifiée `POST /api/v1/merchants/{id}/data/deletion-request`, permission `merchant.delete_data`
- **Entrée** : `{ merchantId: uuid, actingUserId: uuid (depuis le contexte authentifié), password: string }`
- **Sortie** : `{ confirmationToken: string, expiresAt: datetime }`
- **Préconditions** : le merchant est celui du tenant authentifié; le mot de passe de l'utilisateur courant est réauthentifié via le port Identity exposé à l'application Backup.
- **Postconditions** : jeton cryptographiquement aléatoire, à usage unique, lié au merchant, valable 15 minutes; seul son hash est persisté. Le jeton brut n'est retourné qu'une fois et n'est jamais journalisé.
- **Erreurs** : `401 INVALID_CREDENTIALS` (mot de passe incorrect), `403 FORBIDDEN` (permission/scope refusé).
- **Événements publiés** : aucun; `MerchantDataDeleted` est publié seulement par `DeleteAllMerchantDataUseCase` après confirmation.

### Consommation de `MerchantDataDeleted`
Chaque bounded context consomme cet événement de façon idempotente (INV-TR-03), ne purge que ses propres données et publie `MerchantDataPurged { context, merchantId }` dans sa propre Outbox une fois sa purge locale terminée. Les agrégats sont purgés dans des transactions distinctes conformément à INV-TR-01; le marqueur de purge et l'événement final sont atomiques. Détails par contexte et rétention d'audit : `docs/16-business-invariants-and-rules.md`.

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

### `ReconcileOrderStatusFromMessageUseCase`
- **Déclencheur** : `MessageEvaluated` dont `extractedData.intent` est configure a `payment_received` ou `delivery_confirmed`.
- **Entrée** : `{ eventId: uuid, merchantId: uuid, contactId: uuid, intent: "payment_received"|"delivery_confirmed", sourceMessageId: uuid, sourceMessageTimestamp: datetime }`
- **Sortie** : `{ outcome: "updated"|"ignored"|"already_processed", orderId?: uuid, status?: string }`
- **Préconditions** : dernier Order ouvert compatible du merchant/contact dans `ORDER_DETECTION_CORRELATION_WINDOW_DAYS`; paiement cible `pending_payment`, livraison cible `paid_not_delivered`.
- **Postconditions** : aucun Order cree; transition faite par l'agregat, avec Outbox et marqueur idempotent dans la meme transaction.
- **Erreurs** : `409 INVALID_ORDER_TRANSITION`; absence de cible compatible retourne `ignored`.
- **Événements publiés** : `OrderStatusChanged` uniquement si transition effectuee.

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

## Contexte : CRM

### `ListContactsUseCase`
- **Mode d'entrée** : route protégée par `contact.read`
- **Entrée** : `{ merchantId: uuid, segmentId?: uuid, page?: number, pageSize?: number }`
- **Sortie** : `{ contacts: ContactSummary[], totalCount: number }`
- **Postconditions** : les résultats sont limités au merchant issu du tenant context; si `segmentId` est fourni, seuls les contacts membres du segment sont retournés.

### `UpdateContactFromMessageUseCase`
- **Déclencheur** : événement `MessageReceived`
- **Entrée** : `{ merchantId: uuid, platformConnectionId: uuid, externalIdentifier: string, displayName: string, timestamp: datetime }`
- **Sortie** : `{ contactId: uuid, isNewContact: boolean }`
- **Postconditions** : jamais de doublon créé si `externalIdentifier` déjà connu, même si `displayName` a changé

### `UpdateContactFromOrderUseCase`
- **Déclencheur** : événement `OrderStatusChanged` (statut = `paid_and_delivered`)
- **Entrée** : `{ contactId: uuid, orderAmount: Money }`
- **Sortie** : `{ contactId: uuid, spendingByCurrency: Money[], orderCount: number, loyaltyScore: number }`

### `CreateSegmentUseCase`
- **Entrée** : `{ merchantId: uuid, name: string, definitionRule: { field: string, operator: ">"|"<"|"="|"contains", value: any, currency?: string } }` (`currency` obligatoire quand `field = totalSpent`, voir INV-CRM-08)
- **Sortie** : `{ segmentId: uuid }`
- **Erreurs** : `400 UNKNOWN_FIELD`, `400 UNSUPPORTED_OPERATOR`, `400 CURRENCY_REQUIRED`

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
- **Événements publiés** : `RelationshipAnomalyDetected` (par anomalie), via Outbox CRM uniquement

### `MergeContactsUseCase`
- **Entrée** : `{ primaryContactId: uuid, duplicateContactId: uuid, merchantId: uuid }`
- **Sortie** : `{ mergedContactId: uuid, mergedOrderCount: number }`
- **Préconditions** : action manuelle uniquement (déclenchée par le merchant, jamais automatique — voir invariants)
- **Postconditions** : trace d'audit de la fusion conservée

---

## Convention obligatoire de nommage des paramètres (pour cohérence inter-fichiers)

- Tout identifiant : suffixe `Id`, type `uuid` (jamais un entier auto-incrémenté exposé publiquement)
- Tout montant : toujours objet `Money { amount, currency }`, jamais un nombre nu dans un contrat d'entrée/sortie
- Toute date : ISO 8601 avec fuseau horaire explicite (`datetime`)
- Toute énumération de statut : chaîne explicite en `snake_case`, jamais un entier magique


## Mode d'entrée d'un Use Case (règle de complétude)

Chaque Use Case a **un seul** mode d'entrée : route API (avec permission déclarée), consommateur d'événement, job planifié, ou usage interne. Un Use Case déclenché par événement ou job n'a **pas** de route. Un Use Case est « terminé » quand son mode d'entrée existe, est testé, et que les routes sont protégées par `@requires_permission` (ou `@public_route`, voir `21-middleware-layer.md`).

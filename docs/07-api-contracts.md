# Contrats d'API par contexte

Convention : REST, JSON, versionné dès le départ (`/api/v1/...`). Chaque endpoint appelle **un seul** Use Case — pas d'endpoint "fourre-tout".

---

## Contexte : Platform Connectors

### `POST /api/v1/platform-connections`
Connecter un nouveau compte plateforme.
```json
// Requête
{ "platformType": "whatsapp", "externalAccountId": "string", "oauthCode": "string", "consentGiven": true }
// Réponse 201
{ "id": "uuid", "platformType": "whatsapp", "connectionStatus": "active" }
```

### `POST /webhooks/whatsapp` — `POST /webhooks/instagram`
Webhooks entrants, format imposé par chaque plateforme (voir doc officielle de chaque API). Traduits en interne vers l'événement de domaine `MessageReceived`, publié sur le bus.

---

## Contexte : Backup

### `GET /api/v1/backups?platformConnectionId={id}`
Liste des snapshots avec statut.

### `POST /api/v1/backups/{platformConnectionId}/restore`
Déclenche un export de restauration.
```json
// Réponse 202 (traitement async)
{ "exportJobId": "uuid", "status": "processing" }
```

### `GET /api/v1/backups/exports/{exportJobId}`
```json
{ "status": "ready", "downloadUrl": "https://..." }
```

### `GET /api/v1/backups/objects/{reference}`
Téléchargement via URL signée temporaire; signature HMAC et expiration obligatoires.

---

## Contexte : Order Detection

### `GET /api/v1/dashboard/dormant-money`
```json
{
  "totalDormantAmount": { "amount": 340000, "currency": "XOF" },
  "orders": [
    { "id": "uuid", "contactName": "string", "amount": { "amount": 15000, "currency": "XOF" },
      "status": "pending_payment", "hoursSinceCreated": 36, "confidenceScore": 87 }
  ]
}
```

### `PATCH /api/v1/orders/{id}/status`
```json
// Requête
{ "newStatus": "paid_not_delivered" }
// Réponse 200 — 409 si transition invalide (voir machine à états dans 02-domain-model.md)
```

### `POST /api/v1/orders/{id}/reminders`
Déclenche/planifie une relance manuelle ou confirme une relance suggérée automatiquement.

---

## Contexte : CRM

### `GET /api/v1/contacts?segment={segmentId}`
Liste paginée des contacts d'un segment.

### `POST /api/v1/segments`
```json
{ "name": "Clients VIP", "definitionRule": { "field": "totalSpent", "operator": ">", "value": 50000 } }
```

### `POST /api/v1/segments/{id}/bulk-message`
```json
{ "template": "Bonjour {prenom}, une promo rien que pour vous...", "channel": "whatsapp" }
// Réponse 202 — traitement async, respecte les rate limits de la plateforme (voir 04-tech-stack-infrastructure.md §2.3)
```

---

## Codes d'erreur standards (tous contextes)

| Code | Signification |
|---|---|
| 400 | Requête malformée / Value Object invalide (ex : devise inconnue) |
| 401 / 403 | Authentification / autorisation |
| 404 | Ressource introuvable |
| 409 | Conflit — transition d'état invalide, violation d'invariant de domaine |
| 422 | Règle métier violée (ex : limite de plan atteinte) |
| 429 | Rate limit atteint (interne ou reporté depuis une plateforme externe) |
| 503 | Plateforme externe indisponible (WhatsApp/Meta down) |

Chaque erreur 4xx/5xx retourne un corps standard :
```json
{ "errorCode": "INVALID_ORDER_TRANSITION", "message": "...", "details": {} }
```


---

## Contexte : Identity (routes publiques sauf `POST /merchants`)
- `POST /api/v1/auth/register` : `{ phoneNumber, password, email? }` → 201 `{ userId }`
- `POST /api/v1/auth/login` : `{ phoneNumber, password }` → 200 `{ accessToken, refreshToken, expiresAt }`
- `POST /api/v1/auth/refresh` : `{ refreshToken }` → 200 `{ accessToken, expiresAt }`
- `POST /api/v1/merchants` (authentifiée) : `{ name, country, preferredLanguage, currency }` → 201 `{ merchantId, subscriptionPlan }`

## Contexte : Access Control (toutes protégées par permission)
- `POST /api/v1/roles` (`role.create`) : `{ name, permissions[] }` → 201 `{ roleId }`
- `PUT /api/v1/roles/{id}/permissions` (`role.update`) : `{ permissions[] }` → 200
- `POST /api/v1/role-assignments` (`role.assign`) : `{ userId, roleId, scope }` → 201 `{ roleAssignmentId }`
- `DELETE /api/v1/role-assignments/{id}` (`role.revoke`) → 200 `{ revokedAt }`

## Contexte : Billing
- `GET /api/v1/pricing?country=US` (`@public_route`) → `{ country, plans: [{ code, prices: [{ country, currency, periodDays, amountMinor }], entitlements }] }`; pays exact prioritaire, puis pays `*`, sans conversion de devise.
- `PUT /api/v1/admin/plans/{code}` (`plan.manage`, permission globale) : `{ active?, order?, entitlements? }` → définition et entitlements configurés.
- `PUT /api/v1/admin/plan-prices` (`plan.manage`, permission globale) : `{ planCode, country, currency, periodDays, amountMinor, active? }` → prix explicite.
- `POST /api/v1/trials` (`billing.trial.start`) : `{ cardProvided? }` → essai configuré, une fois par merchant.
- `POST /api/v1/coupons/apply` (`billing.coupon.apply`) : `{ code }` → coupon validé et appliqué une fois.
- `POST /api/v1/referrals/redeem` (`billing.referral.redeem`) : `{ referrerMerchantId }` → parrainage enregistré; récompense différée au premier paiement.
- `PUT /api/v1/admin/trial-policy`, `PUT /api/v1/admin/referral-policy`, `PUT /api/v1/admin/coupons` (`plan.manage`, permission globale) modifient les policies et coupons.
- `POST /api/v1/outbound/estimate` (`outbound.estimate`) : `{ category, count? }` → estimation en unités mineures, sans conversion; `chargeProcessor: "meta_direct"` indique que Meta facture le vendeur.
- `GET /api/v1/outbound/usage` (`outbound.usage.read`) → compteurs API du mois courant par catégorie; les liens manuels ne consomment pas de quota.
- `GET /api/v1/reports/value` (`outbound.usage.read`) → `{ merchantId, country, currency, month, totalAmountMinor, unpricedMessageCount, estimateIncomplete, items: [{ category, messages, priced, unitAmountMinor?, amountMinor?, currency }] }` ; estimation incomplète explicitement signalée quand il manque un tarif.
- `PUT /api/v1/admin/outbound-rates` (`plan.manage`, permission globale) : `{ country, category, currency, amountMinor, validFrom, validUntil?, active? }` → tarif configuré sans redéploiement.
- `POST /api/v1/segments/{id}/bulk-message` accepte `{ deliveryMode?: "manual_link"|"api_send", category, marketingConfirmed?, confirmedEstimate? }`. Le défaut WhatsApp est `manual_link` et retourne les liens sans appel API. `api_send` met en file et réserve le quota au worker; Marketing exige la confirmation de l'estimation courante.
- Aucun tarif Meta n'est seedé en l'absence d'une grille pays/catégorie vérifiée; un tarif absent donne `OUTBOUND_RATE_NOT_CONFIGURED`. Billing n'encaisse jamais les frais Meta.
- Un envoi `api_send` sans tarif actif retourne `422 OUTBOUND_RATE_MISSING` avant réservation de quota; les catégories non tarifées du rapport mensuel sont explicitement comptabilisées via `unpricedMessageCount` et `estimateIncomplete`.
- Refus d'une fonctionnalité non incluse : HTTP 402 `{ errorCode: "PLAN_UPGRADE_REQUIRED", correlationId, missingEntitlement }`.

## Compléments : routes ajoutées après coup et permission de chaque route

### Routes ajoutées

- `GET /api/v1/detection-candidates` : candidats en attente (`ListPendingDetectionCandidatesUseCase`)
- `POST /api/v1/detection-candidates/{id}/decision` : `{ decision: "validate"|"reject" }` → 200 (`ValidateOrRejectDetectionUseCase`)
- `GET /api/v1/segments/{id}/members` : membres d'un segment, paginé (`GetSegmentMembersUseCase`)
- `POST /api/v1/contacts/merge` : `{ primaryContactId, duplicateContactId }` → 202 `{ primaryContactId, mergedContactId, status: "merge_in_progress" }`
- `PUT /api/v1/rule-sets/{scope}` : `{ rules[] }` → 200 `{ ruleSetId, version }` (`UpdateRuleSetUseCase`)
- `POST /api/v1/merchants/{id}/data/deletion-request` : `{ password }` → 201 `{ confirmationToken, expiresAt }` (`RequestMerchantDeletionUseCase`); réauthentification obligatoire, jeton à usage unique valable 15 minutes
- `DELETE /api/v1/merchants/{id}/data` : `{ confirmationToken }` → 200 `{ deletedAt }` (`DeleteAllMerchantDataUseCase`)

### Permission par route

Le `merchantId` vient toujours du `TenantIsolationMiddleware`.

| Route | Permission / politique |
|---|---|
| `POST /api/v1/platform-connections` | `platform.connect` |
| `GET /api/v1/backups`, `GET /api/v1/backups/exports/{id}` | `backup.read` |
| `POST /api/v1/backups/{id}/restore` | `backup.restore` |
| `GET /api/v1/backups/objects/{reference}` | `@public_route` avec signature HMAC temporaire obligatoire |
| `DELETE /api/v1/merchants/{id}/data` | `merchant.delete_data` |
| `POST /api/v1/merchants/{id}/data/deletion-request` | `merchant.delete_data` |
| `GET /api/v1/dashboard/dormant-money` | `order.read` |
| `PATCH /api/v1/orders/{id}/status` | `order.update_status` |
| `POST /api/v1/orders/{id}/reminders` | `order.remind` |
| `GET /api/v1/detection-candidates`, `POST /api/v1/detection-candidates/{id}/decision` | `order.review` |
| `GET /api/v1/contacts`, `GET /api/v1/segments/{id}/members` | `contact.read` |
| `POST /api/v1/contacts/merge` | `contact.merge` |
| `POST /api/v1/segments` | `segment.create` |
| `POST /api/v1/segments/{id}/bulk-message` | `segment.bulk_message` |
| `PUT /api/v1/rule-sets/{scope}` | `rule_config.edit` ; les scopes global et pays exigent une assignation de rôle globale |
| `POST /api/v1/webhooks/whatsapp`, `POST /api/v1/webhooks/instagram` | `@public_route` avec vérification de signature obligatoire (INV-PC-02) |

Les use cases déclenchés par événement ou job (synchronisation, évaluation, snapshots, relances planifiées, anomalies) n'ont pas de route.

### Contrat de suppression des données merchant

`POST /api/v1/merchants/{id}/data/deletion-request` exige le mot de passe de l'utilisateur authentifié dans `{ "password": "..." }`. La réponse `201` contient `{ "confirmationToken": "...", "expiresAt": "..." }`. Le jeton brut est présenté ensuite une seule fois à `DELETE /api/v1/merchants/{id}/data`; seul son hash est stocké et aucun middleware, contrôleur ou journal ne doit en conserver le contenu. Un jeton invalide, expiré ou déjà consommé retourne `403 INVALID_CONFIRMATION_TOKEN`. Les deux routes appliquent `merchant.delete_data`, le contrôle de scope du tenant et le middleware standard d'exception.

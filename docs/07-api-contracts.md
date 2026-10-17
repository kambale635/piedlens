# Contrats d'API par contexte

Convention : REST, JSON, versionné dès le départ (`/api/v1/...`). Chaque endpoint appelle **un seul** Use Case — pas d'endpoint "fourre-tout".

---

## Contexte : Platform Connectors

### `POST /api/v1/platform-connections`
Connecter un nouveau compte plateforme.
```json
// Requête
{ "platformType": "whatsapp", "externalAccountId": "string", "oauthCode": "string" }
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

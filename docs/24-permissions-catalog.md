# Catalogue des permissions

Catalogue extrait des vues enregistrées dans le resolver Django, via leur attribut `required_permission` posé par `@requires_permission`.

| Permission | Contexte | Routes protégées |
|---|---|---|
| `role.create` | Access Control | `POST /api/v1/roles` |
| `role.update` | Access Control | `PUT /api/v1/roles/{role_id}/permissions` |
| `role.assign` | Access Control | `POST /api/v1/role-assignments` |
| `role.revoke` | Access Control | `DELETE /api/v1/role-assignments/{role_assignment_id}` |
| `platform.connect` | Platform Connectors | `POST /api/v1/platform-connections` |
| `backup.read` | Backup | `GET /api/v1/backups`, `GET /api/v1/backups/exports/{export_job_id}` |
| `backup.restore` | Backup | `POST /api/v1/backups/{platform_connection_id}/restore` |
| `@public_route` | Backup | `GET /api/v1/backups/objects/{reference}` (signature temporaire obligatoire) |
| `merchant.delete_data` | Backup | `DELETE /api/v1/merchants/{merchant_id}/data` |
| `order.read` | Order Detection | `GET /api/v1/dashboard/dormant-money` |
| `order.update_status` | Order Detection | `PATCH /api/v1/orders/{order_id}/status` |
| `order.remind` | Order Detection | `POST /api/v1/orders/{order_id}/reminders` |
| `order.review` | Order Detection | `GET /api/v1/detection-candidates`, `POST /api/v1/detection-candidates/{candidate_id}/decision` |
| `contact.read` | CRM | `GET /api/v1/contacts`, `GET /api/v1/segments/{segment_id}/members` |
| `contact.merge` | CRM | `POST /api/v1/contacts/merge` |
| `segment.create` | CRM | `POST /api/v1/segments` |
| `segment.bulk_message` | CRM | `POST /api/v1/segments/{segment_id}/bulk-message` |
| `rule_config.edit` | Rules Engine | `PUT /api/v1/rule-sets/{scope}` (global/country scopes also require a global role assignment) |
| `plan.manage` | Billing | `PUT /api/v1/admin/plans/{code}`, `PUT /api/v1/admin/plan-prices`, `PUT /api/v1/admin/trial-policy`, `PUT /api/v1/admin/referral-policy`, `PUT /api/v1/admin/coupons`, `PUT /api/v1/admin/outbound-rates` (permission globale) |
| `billing.trial.start` | Billing | `POST /api/v1/trials` |
| `billing.coupon.apply` | Billing | `POST /api/v1/coupons/apply` |
| `billing.referral.redeem` | Billing | `POST /api/v1/referrals/redeem` |
| `outbound.estimate` | Billing | `POST /api/v1/outbound/estimate` |
| `outbound.usage.read` | Billing | `GET /api/v1/outbound/usage`, `GET /api/v1/reports/value` |

Total actuel : 23 permissions, extraites du resolver Django. Les routes `GET /api/v1/pricing` et webhooks documentés ont une politique publique explicite. Les routes publiques Identity et `POST /api/v1/merchants` ont une politique publique explicite. Toute route non marquée `@requires_permission` ou `@public_route` est refusée par défaut.

## Permissions proposées — Commerce social Afrique (non implémentées)

Ne pas compter ces entrées dans le total actuel. Elles deviennent effectives seulement après ajout d'une route protégée, d'une politique et de tests d'accès positif/négatif.

| Permission proposée | Contexte | Routes proposées |
|---|---|---|
| `country_pack.manage` | Country Packs | `PUT /api/v1/admin/country-packs/{code}` (globale) |
| `catalog.read`, `catalog.manage`, `catalog.import` | Catalog | lecture/création produits; import CSV |
| `stock.adjust` | Catalog | `POST /api/v1/catalog/variants/{variant_id}/stock-adjustments` |
| `pricing.manage` | Pricing | `PUT /api/v1/pricing/price-lists` |
| `negotiation.use` | Pricing | création proposition et décision vendeur |
| `fx.read`, `fx.manage` | Currency Rates | `GET/PUT /api/v1/fx/rates` |
| `mm.proof.submit` | Mobile Money | `POST /api/v1/orders/{order_id}/payment-proofs` |
| `mm.configure` | Mobile Money | route admin plateforme pour réseaux |
| `@public_route` | Mobile Money | `POST /api/v1/webhooks/mobile-money/{network_code}`, signature horodatée et anti-rejeu requis |
| `supplier.read`, `supplier.manage` | Supplier Network | lecture/création profils, dépôt de vérification |
| `supplier.verify` | Supplier Network | revue plateforme globale (`POST .../review`) |
| `po.read`, `po.create`, `po.manage` | Supplier Network | consultation, création et gestion bons de commande |
| `delivery.manage` | Logistics | création/gestion merchant des livraisons |
| `delivery.update` | Logistics | statut/remise, restreint aux livraisons du livreur assigné |
| `storefront.manage`, `storefront.read` | Storefront | cartes/vitrine merchant; lecture publique limitée par `@public_route` |
| `whatsapp.import` | Onboarding | import/collage avec consentement |
| `@public_route` | Storefront | `GET /api/v1/storefront/{slug}`, contenu publié et sans PII |

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
| `plan.manage` | Billing | `PUT /api/v1/admin/plans/{code}`, `PUT /api/v1/admin/plan-prices` (permission globale) |

Total : 18 permissions, extraites du resolver Django. `GET /api/v1/pricing` est explicitement public. Les routes `POST /api/v1/webhooks/whatsapp` et `POST /api/v1/webhooks/instagram` sont `@public_route` et valident leur signature avant tout traitement (INV-PC-02); elles n'ajoutent pas de permission. Les routes publiques Identity et `POST /api/v1/merchants` ont une politique publique explicite. Les use cases déclenchés par événement ou job n'ont pas de route. Toute route non marquée `@requires_permission` ou `@public_route` est refusée par défaut.

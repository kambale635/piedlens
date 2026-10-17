# CRM

Maintains merchant contacts, dynamic segments, relationship signals, and bulk messaging.

Reference: [docs/12-context-crm.md](../../../docs/12-context-crm.md).

Use Cases implemented: UpdateContactFromMessageUseCase, UpdateContactFromOrderUseCase, CreateSegmentUseCase, GetSegmentMembersUseCase, SendBulkMessageUseCase, DetectRelationshipAnomalyUseCase, MergeContactsUseCase, and the idempotent `ContactMerged` consumer.

Contacts are keyed by `(merchant_id, platform_connection_id, external_identifier)`; display name is mutable profile data only. The `MessageReceived` event's processed marker and Contact changes commit together through `DjangoCRMUnitOfWork`. Initial `total_spent` currency is supplied by an injected merchant-defaults provider.

Delivered-order events update `total_spent_by_currency`, `order_count`, and the CRM-owned `purchase_history` only when status is `paid_and_delivered` (INV-CRM-04). The event's `updated_at` is the recorded purchase date; repeated `order_id` values do not count twice. The amount is carried in `OrderStatusChanged`; each currency is added through `Money.add()` with no implicit conversion. Loyalty scoring remains an injected domain-service contract because its exact business formula is not yet specified.

`ContactMerged` is the only other trigger allowed to update `total_spent_by_currency` and `order_count` (INV-CRM-04). Its consumer absorbs the immutable duplicate snapshot into only the primary Contact and records the `processed_events` marker in the same transaction (INV-TR-01/03).

CRM producer events are persisted by `DjangoCRMOutbox` in `crm_outbox_events`. The adapter uses the active `DjangoCRMUnitOfWork` transaction, so business writes and Outbox records commit or roll back together (INV-TR-02). Redis publication remains the responsibility of an Outbox relay.

CRM segments are persisted as declarative rules in `crm_segments`; membership is calculated dynamically and paginated. `total_spent` rules carry a `Money` threshold and compare only that currency; tag `contains` uses exact membership. Membership pages use the Redis adapter with a five-minute default TTL and a merchant-version namespace; Contact writes invalidate that namespace after commit.

Relationship-anomaly notification records are unique by `(contact_id, last_purchase_order_id)`; the notification row and `RelationshipAnomalyDetected` Outbox event are written within the same CRM UnitOfWork (INV-CRM-06).

`DetectRelationshipAnomalyUseCase` evaluates the CRM-owned purchase history using settings-backed defaults and optional merchant overrides for `min_purchases`, `anomaly_multiplier`, and `min_inactivity_days`. It emits one notification and Outbox event per silence period; it never reads Order Detection tables (INV-CRM-05/06, INV-TR-04).

Tests: `PYTHONPATH=src python -m unittest tests.unit.crm.test_update_contact_from_message_use_case`; Django integration: `python manage.py test tests.integration.crm --settings=config.test_settings`.
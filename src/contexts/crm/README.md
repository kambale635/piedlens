# CRM

Maintains merchant contacts, dynamic segments, relationship signals, and bulk messaging.

Reference: [docs/12-context-crm.md](../../../docs/12-context-crm.md).

Use Cases implemented: UpdateContactFromMessageUseCase and UpdateContactFromOrderUseCase. CreateSegmentUseCase, GetSegmentMembersUseCase, SendBulkMessageUseCase, DetectRelationshipAnomalyUseCase, and MergeContactsUseCase remain catalogued in [docs/15-use-cases-catalog.md](../../../docs/15-use-cases-catalog.md#contexte-crm).

Contacts are keyed by `(merchant_id, platform_connection_id, external_identifier)`; display name is mutable profile data only. The `MessageReceived` event's processed marker and Contact changes commit together through `DjangoCRMUnitOfWork`. Initial `total_spent` currency is supplied by an injected merchant-defaults provider.

Delivered-order events update `total_spent_by_currency` and `order_count` only when status is `paid_and_delivered` (INV-CRM-04). The amount is carried in `OrderStatusChanged`; each currency is added through `Money.add()` with no implicit conversion. Loyalty scoring remains an injected domain-service contract because its exact business formula is not yet specified.

Tests: `PYTHONPATH=src python -m unittest tests.unit.crm.test_update_contact_from_message_use_case`; Django integration: `python manage.py test tests.integration.crm --settings=config.test_settings`.
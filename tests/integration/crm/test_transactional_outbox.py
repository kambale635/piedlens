from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from django.test import TransactionTestCase

from contexts.crm.infrastructure.django_crm_outbox import DjangoCRMOutbox
from contexts.crm.infrastructure.django_unit_of_work import DjangoCRMUnitOfWork
from contexts.crm.infrastructure.models import ContactRecord, OutboxEventRecord


@dataclass(frozen=True)
class ContactChanged:
    event_id: UUID
    contact_id: UUID
    occurred_at: datetime


class CRMTransactionalOutboxIntegrationTests(TransactionTestCase):
    """Verify business rows and CRM Outbox events share one ACID boundary."""

    def setUp(self):
        self.unit_of_work = DjangoCRMUnitOfWork()
        self.outbox = DjangoCRMOutbox()

    def create_contact_record(self, contact_id):
        ContactRecord.objects.create(
            id=contact_id,
            merchant_id=uuid4(),
            platform_connection_id=uuid4(),
            external_identifier=str(contact_id),
            display_name="Customer",
            total_spent_by_currency={},
            order_count=0,
            last_interaction_at=datetime.now(timezone.utc),
            loyalty_score=0,
            tags=[],
        )

    def test_business_write_and_outbox_event_commit_together(self):
        contact_id = uuid4()
        event = ContactChanged(uuid4(), contact_id, datetime.now(timezone.utc))

        with self.unit_of_work:
            self.create_contact_record(contact_id)
            self.outbox.add(event)

        self.assertTrue(ContactRecord.objects.filter(id=contact_id).exists())
        outbox_record = OutboxEventRecord.objects.get(event_id=event.event_id)
        self.assertEqual(outbox_record.event_type, "ContactChanged")
        self.assertEqual(outbox_record.produced_by, "crm")
        self.assertEqual(outbox_record.payload, {"contact_id": str(contact_id)})

    def test_business_write_and_outbox_event_roll_back_together(self):
        contact_id = uuid4()
        event = ContactChanged(uuid4(), contact_id, datetime.now(timezone.utc))

        with self.assertRaisesRegex(RuntimeError, "force rollback"):
            with self.unit_of_work:
                self.create_contact_record(contact_id)
                self.outbox.add(event)
                raise RuntimeError("force rollback")

        self.assertFalse(ContactRecord.objects.filter(id=contact_id).exists())
        self.assertFalse(OutboxEventRecord.objects.exists())
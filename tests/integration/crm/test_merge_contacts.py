from datetime import datetime, timezone
from uuid import uuid4

from django.test import TransactionTestCase

from contexts.crm.application.use_cases.consume_contact_merged_use_case import (
    ConsumeContactMergedUseCase,
)
from contexts.crm.domain.events.crm_events import ContactMerged, MergedContactSnapshot
from contexts.crm.application.use_cases.merge_contacts_use_case import MergeContactsUseCase
from contexts.crm.domain.entities.contact import Contact
from contexts.crm.domain.value_objects.contact_status import ContactStatus
from contexts.crm.infrastructure.persistence.django_contact_repository import DjangoContactRepository
from contexts.crm.infrastructure.messaging.django_crm_outbox import DjangoCRMOutbox
from contexts.crm.infrastructure.persistence.django_processed_message_repository import (
    DjangoProcessedMessageRepository,
)
from contexts.crm.infrastructure.persistence.django_unit_of_work import DjangoCRMUnitOfWork
from contexts.crm.infrastructure.persistence.models import ContactRecord, OutboxEventRecord
from shared_kernel.value_objects.money import Money


class MergeContactsIntegrationTests(TransactionTestCase):
    """Prove the duplicate tombstone and ContactMerged Outbox share one transaction."""

    def setUp(self):
        self.merchant_id = uuid4()
        self.contact_repository = DjangoContactRepository()
        self.unit_of_work = DjangoCRMUnitOfWork()
        self.outbox = DjangoCRMOutbox()
        self.primary = self.create_contact("primary", "15", "XOF")
        self.duplicate = self.create_contact("duplicate", "9.50", "USD")
        self.use_case = MergeContactsUseCase(
            contact_repository=self.contact_repository,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
        )

    def create_contact(self, external_identifier, amount, currency):
        contact = Contact.create(
            merchant_id=self.merchant_id,
            platform_connection_id=uuid4(),
            external_identifier=external_identifier,
            display_name=external_identifier,
            initial_total_spent=Money(amount, currency),
            occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
        )
        with self.unit_of_work:
            self.contact_repository.get_or_create(contact)
        return contact

    def test_duplicate_tombstone_and_merge_event_commit_atomically(self):
        result = self.use_case.execute(
            primary_contact_id=self.primary.id,
            duplicate_contact_id=self.duplicate.id,
            merchant_id=self.merchant_id,
        )

        primary_record = ContactRecord.objects.get(id=self.primary.id)
        duplicate_record = ContactRecord.objects.get(id=self.duplicate.id)
        outbox_record = OutboxEventRecord.objects.get()
        self.assertEqual(result.status, "merge_in_progress")
        self.assertEqual(primary_record.status, ContactStatus.ACTIVE.value)
        self.assertIsNone(primary_record.merged_into_contact_id)
        self.assertEqual(duplicate_record.status, ContactStatus.MERGED.value)
        self.assertEqual(duplicate_record.merged_into_contact_id, self.primary.id)
        self.assertEqual(outbox_record.event_type, "ContactMerged")
        self.assertEqual(outbox_record.produced_by, "crm")
        self.assertEqual(outbox_record.payload["merchant_id"], str(self.merchant_id))
        self.assertEqual(outbox_record.payload["primary_contact_id"], str(self.primary.id))
        self.assertEqual(outbox_record.payload["merged_contact_id"], str(self.duplicate.id))
        self.assertEqual(
            outbox_record.payload["snapshot"]["total_spent_by_currency"],
            [{"amount": "9.50", "currency": "USD"}],
        )

    def test_outbox_failure_rolls_back_duplicate_tombstone(self):
        class FailingOutbox:
            def add(self, event):
                raise RuntimeError("force outbox failure")

        use_case = MergeContactsUseCase(
            contact_repository=self.contact_repository,
            unit_of_work=self.unit_of_work,
            outbox=FailingOutbox(),
        )

        with self.assertRaisesRegex(RuntimeError, "force outbox failure"):
            use_case.execute(
                primary_contact_id=self.primary.id,
                duplicate_contact_id=self.duplicate.id,
                merchant_id=self.merchant_id,
            )

        duplicate_record = ContactRecord.objects.get(id=self.duplicate.id)
        self.assertEqual(duplicate_record.status, ContactStatus.ACTIVE.value)
        self.assertIsNone(duplicate_record.merged_into_contact_id)
        self.assertFalse(OutboxEventRecord.objects.exists())

    def test_merge_consumer_absorbs_snapshot_once_with_processed_marker(self):
        event = ContactMerged(
            event_id=uuid4(),
            occurred_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
            merchant_id=self.merchant_id,
            primary_contact_id=self.primary.id,
            merged_contact_id=self.duplicate.id,
            snapshot=MergedContactSnapshot(
                total_spent_by_currency=(Money("4", "XOF"), Money("2", "USD")),
                order_count=2,
                purchase_history=(),
                tags=("vip",),
            ),
        )
        consumer = ConsumeContactMergedUseCase(
            contact_repository=self.contact_repository,
            processed_events=DjangoProcessedMessageRepository(),
            unit_of_work=self.unit_of_work,
        )

        first = consumer.execute(event)
        replay = consumer.execute(event)

        primary_record = ContactRecord.objects.get(id=self.primary.id)
        self.assertTrue(first.applied)
        self.assertFalse(replay.applied)
        self.assertEqual(
            primary_record.total_spent_by_currency,
            {"XOF": "19", "USD": "2"},
        )
        self.assertEqual(primary_record.order_count, 2)
        self.assertEqual(primary_record.tags, ["vip"])

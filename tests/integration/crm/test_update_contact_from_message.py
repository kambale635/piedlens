from datetime import datetime, timezone
from uuid import uuid4

from django.test import TransactionTestCase

from contexts.crm.application.use_cases.update_contact_from_message_use_case import (
    UpdateContactFromMessageUseCase,
)
from contexts.crm.infrastructure.persistence.django_contact_repository import DjangoContactRepository
from contexts.crm.infrastructure.persistence.django_processed_message_repository import (
    DjangoProcessedMessageRepository,
)
from contexts.crm.infrastructure.persistence.django_unit_of_work import DjangoCRMUnitOfWork
from contexts.crm.infrastructure.persistence.models import ContactRecord, ProcessedMessageRecord
from shared_kernel.value_objects.money import Money


class UpdateContactFromMessageIntegrationTests(TransactionTestCase):
    """Exercise composite identity, event replay, and atomic CRM persistence."""

    def setUp(self):
        class MerchantDefaults:
            def initial_total_spent(self, merchant_id):
                return Money("0", "XOF")

        self.use_case = UpdateContactFromMessageUseCase(
            contact_repository=DjangoContactRepository(),
            defaults_provider=MerchantDefaults(),
            processed_messages=DjangoProcessedMessageRepository(),
            unit_of_work=DjangoCRMUnitOfWork(),
        )
        self.merchant_id = uuid4()
        self.connection_id = uuid4()
        self.external_identifier = "platform-customer-123"

    def send(self, event_id, display_name, timestamp, connection_id=None):
        return self.use_case.execute(
            event_id=event_id,
            merchant_id=self.merchant_id,
            platform_connection_id=connection_id or self.connection_id,
            external_identifier=self.external_identifier,
            display_name=display_name,
            timestamp=timestamp,
        )

    def test_name_change_updates_existing_contact_and_processed_event_atomically(self):
        event_id = uuid4()
        first_result = self.send(
            event_id,
            "Customer One",
            datetime(2026, 9, 20, tzinfo=timezone.utc),
        )
        second_result = self.send(
            uuid4(),
            "Customer Renamed",
            datetime(2026, 9, 21, tzinfo=timezone.utc),
        )

        contact = ContactRecord.objects.get()
        self.assertTrue(first_result.is_new_contact)
        self.assertFalse(second_result.is_new_contact)
        self.assertEqual(first_result.contact_id, second_result.contact_id)
        self.assertEqual(ContactRecord.objects.count(), 1)
        self.assertEqual(contact.display_name, "Customer Renamed")
        self.assertEqual(contact.total_spent_by_currency, {"XOF": "0"})
        self.assertEqual(contact.order_count, 0)
        self.assertEqual(ProcessedMessageRecord.objects.count(), 2)

    def test_same_event_replay_does_not_apply_stale_profile_again(self):
        event_id = uuid4()
        first_result = self.send(
            event_id,
            "Current Name",
            datetime(2026, 9, 22, tzinfo=timezone.utc),
        )
        replay_result = self.send(
            event_id,
            "Stale Name",
            datetime(2026, 9, 19, tzinfo=timezone.utc),
        )

        contact = ContactRecord.objects.get()
        self.assertEqual(first_result.contact_id, replay_result.contact_id)
        self.assertEqual(contact.display_name, "Current Name")
        self.assertEqual(contact.last_interaction_at, datetime(2026, 9, 22, tzinfo=timezone.utc))
        self.assertEqual(ProcessedMessageRecord.objects.count(), 1)

    def test_same_external_identifier_on_distinct_connections_stays_separate(self):
        first = self.send(
            uuid4(),
            "Connection A",
            datetime(2026, 9, 20, tzinfo=timezone.utc),
        )
        second = self.send(
            uuid4(),
            "Connection B",
            datetime(2026, 9, 20, tzinfo=timezone.utc),
            connection_id=uuid4(),
        )

        self.assertNotEqual(first.contact_id, second.contact_id)
        self.assertEqual(ContactRecord.objects.count(), 2)
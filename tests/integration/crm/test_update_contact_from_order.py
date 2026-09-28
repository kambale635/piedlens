from datetime import datetime, timezone
from uuid import uuid4

from django.test import TransactionTestCase

from contexts.crm.application.update_contact_from_order_use_case import (
    UpdateContactFromOrderUseCase,
)
from contexts.crm.domain.contact import Contact
from contexts.crm.domain.loyalty_score import LoyaltyScore
from contexts.crm.infrastructure.django_contact_repository import DjangoContactRepository
from contexts.crm.infrastructure.django_processed_message_repository import (
    DjangoProcessedMessageRepository,
)
from contexts.crm.infrastructure.django_unit_of_work import DjangoCRMUnitOfWork
from contexts.crm.infrastructure.models import ContactRecord, ProcessedMessageRecord
from shared_kernel.value_objects.money import Money


class UpdateContactFromOrderIntegrationTests(TransactionTestCase):
    """Exercise event-idempotent, currency-safe CRM order aggregation via Django ORM."""

    def setUp(self):
        class LoyaltyCalculator:
            def calculate(self, contact):
                return LoyaltyScore(min(contact.order_count * 7, 100))

        self.contact_repository = DjangoContactRepository()
        self.unit_of_work = DjangoCRMUnitOfWork()
        self.use_case = UpdateContactFromOrderUseCase(
            contact_repository=self.contact_repository,
            loyalty_score_calculator=LoyaltyCalculator(),
            processed_messages=DjangoProcessedMessageRepository(),
            unit_of_work=self.unit_of_work,
        )
        self.contact = Contact.create(
            merchant_id=uuid4(),
            platform_connection_id=uuid4(),
            external_identifier="crm-customer",
            display_name="Customer",
            initial_total_spent=Money("0", "XOF"),
            occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
        )
        with self.unit_of_work:
            self.contact_repository.get_or_create(self.contact)

    def process(
        self,
        event_id,
        amount,
        status="paid_and_delivered",
        order_id=None,
        updated_at=None,
    ):
        return self.use_case.execute(
            event_id=event_id,
            contact_id=self.contact.id,
            order_id=order_id or uuid4(),
            status=status,
            order_amount=amount,
            updated_at=updated_at or datetime(2026, 9, 22, tzinfo=timezone.utc),
        )

    def test_paid_delivered_events_accumulate_by_currency_once(self):
        xof_event_id = uuid4()
        usd_event_id = uuid4()
        self.process(xof_event_id, Money("1500", "XOF"))
        self.process(usd_event_id, Money("12.50", "USD"))
        replay = self.process(usd_event_id, Money("12.50", "USD"))

        contact_record = ContactRecord.objects.get(id=self.contact.id)
        self.assertEqual(contact_record.total_spent_by_currency, {"XOF": "1500", "USD": "12.50"})
        self.assertEqual(contact_record.order_count, 2)
        self.assertEqual(contact_record.loyalty_score, 14)
        self.assertFalse(replay.applied)
        self.assertEqual(ProcessedMessageRecord.objects.count(), 2)

    def test_purchase_history_stores_event_date_and_deduplicates_order_id(self):
        order_id = uuid4()
        purchase_date = datetime(2026, 9, 22, 14, 30, tzinfo=timezone.utc)
        self.process(
            uuid4(),
            Money("40", "XOF"),
            order_id=order_id,
            updated_at=purchase_date,
        )
        self.process(
            uuid4(),
            Money("40", "XOF"),
            order_id=order_id,
            updated_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )

        record = ContactRecord.objects.get(id=self.contact.id)
        self.assertEqual(record.order_count, 1)
        self.assertEqual(record.total_spent_by_currency, {"XOF": "40"})
        self.assertEqual(
            record.purchase_history,
            [{"order_id": str(order_id), "purchased_at": purchase_date.isoformat()}],
        )
        with self.unit_of_work:
            rehydrated = self.contact_repository.find_for_update_by_id(self.contact.id)
        self.assertEqual(rehydrated.purchase_history[0].purchased_at, purchase_date)

    def test_other_order_status_is_processed_without_mutating_contact(self):
        event_id = uuid4()

        result = self.process(event_id, Money("40", "XOF"), status="paid_not_delivered")

        contact_record = ContactRecord.objects.get(id=self.contact.id)
        self.assertFalse(result.applied)
        self.assertEqual(contact_record.total_spent_by_currency, {"XOF": "0"})
        self.assertEqual(contact_record.order_count, 0)
        self.assertEqual(contact_record.loyalty_score, 0)
        self.assertEqual(ProcessedMessageRecord.objects.count(), 1)

    def test_contact_totals_roll_back_if_processed_marker_write_fails(self):
        class FailingProcessedRepository:
            def has_processed(self, event_id, consumer_name):
                return False

            def mark_processed(self, event_id, consumer_name):
                raise RuntimeError("force processed marker failure")

        class LoyaltyCalculator:
            def calculate(self, contact):
                return LoyaltyScore(50)

        use_case = UpdateContactFromOrderUseCase(
            contact_repository=self.contact_repository,
            loyalty_score_calculator=LoyaltyCalculator(),
            processed_messages=FailingProcessedRepository(),
            unit_of_work=self.unit_of_work,
        )
        event_id = uuid4()

        with self.assertRaises(RuntimeError):
            use_case.execute(
                event_id=event_id,
                contact_id=self.contact.id,
                order_id=uuid4(),
                status="paid_and_delivered",
                order_amount=Money("75", "XOF"),
                updated_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
            )

        contact_record = ContactRecord.objects.get(id=self.contact.id)
        self.assertEqual(contact_record.total_spent_by_currency, {"XOF": "0"})
        self.assertEqual(contact_record.order_count, 0)
        self.assertEqual(ProcessedMessageRecord.objects.count(), 0)
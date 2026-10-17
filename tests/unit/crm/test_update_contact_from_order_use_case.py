import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.crm.application.use_cases.update_contact_from_order_use_case import (
    UpdateContactFromOrderUseCase,
)
from contexts.crm.domain.entities.contact import Contact
from contexts.crm.domain.value_objects.loyalty_score import LoyaltyScore
from shared_kernel.application_exceptions import ResourceNotFoundException
from shared_kernel.value_objects.money import Money


class InMemoryContactRepository:
    def __init__(self, contact):
        self.contact = contact
        self.saved = []
        self.locked_ids = []

    def find_by_external_identifier(self, merchant_id, platform_connection_id, external_identifier):
        return None

    def find_for_update_by_external_identifier(self, merchant_id, platform_connection_id, external_identifier):
        return None

    def find_for_update_by_id(self, contact_id):
        self.locked_ids.append(contact_id)
        return self.contact if self.contact and self.contact.id == contact_id else None

    def get_or_create(self, contact):
        return contact, True

    def save(self, contact):
        self.saved.append(contact)


class FixedLoyaltyCalculator:
    def __init__(self):
        self.calculated = []

    def calculate(self, contact, primary_currency):
        self.calculated.append((contact, primary_currency))
        return LoyaltyScore(min(contact.order_count * 10, 100))


class MerchantDefaults:
    def primary_currency(self, merchant_id):
        return "XOF"


class InMemoryProcessedMessages:
    def __init__(self):
        self.processed = set()

    def has_processed(self, event_id, consumer_name):
        return (event_id, consumer_name) in self.processed

    def mark_processed(self, event_id, consumer_name):
        self.processed.add((event_id, consumer_name))


class InMemoryUnitOfWork:
    def __init__(self):
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


class UpdateContactFromOrderUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.contact = Contact.create(
            merchant_id=uuid4(),
            platform_connection_id=uuid4(),
            external_identifier="remote-customer",
            display_name="Customer",
            initial_total_spent=Money("0", "XOF"),
            occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
        )
        self.repository = InMemoryContactRepository(self.contact)
        self.loyalty_calculator = FixedLoyaltyCalculator()
        self.processed = InMemoryProcessedMessages()
        self.unit_of_work = InMemoryUnitOfWork()
        self.use_case = UpdateContactFromOrderUseCase(
            contact_repository=self.repository,
            loyalty_score_calculator=self.loyalty_calculator,
            defaults_provider=MerchantDefaults(),
            processed_messages=self.processed,
            unit_of_work=self.unit_of_work,
        )

    def execute(
        self,
        event_id=None,
        status="paid_and_delivered",
        order_amount=None,
        order_id=None,
        updated_at=None,
    ):
        return self.use_case.execute(
            event_id=event_id or uuid4(),
            contact_id=self.contact.id,
            order_id=order_id or uuid4(),
            status=status,
            order_amount=order_amount or Money("25", "XOF"),
            updated_at=updated_at or datetime(2026, 9, 22, tzinfo=timezone.utc),
        )

    def test_delivered_order_updates_totals_separately_by_currency(self):
        result = self.execute(order_amount=Money("125", "XOF"))
        second_result = self.execute(order_amount=Money("30.50", "USD"))

        totals = {amount.currency: amount.amount for amount in second_result.total_spent_by_currency}
        self.assertTrue(result.applied)
        self.assertEqual(totals, {"XOF": Money("125", "XOF").amount, "USD": Money("30.50", "USD").amount})
        self.assertEqual(second_result.order_count, 2)
        self.assertEqual(second_result.loyalty_score, 20)
        self.assertEqual(len(self.repository.saved), 2)
        self.assertEqual([currency for _, currency in self.loyalty_calculator.calculated], ["XOF", "XOF"])

    def test_non_delivered_order_event_is_processed_without_contact_mutation(self):
        event_id = uuid4()
        result = self.execute(event_id=event_id, status="paid_not_delivered")

        self.assertFalse(result.applied)
        self.assertEqual(self.contact.order_count, 0)
        self.assertEqual(self.contact.total_spent_by_currency, (Money("0", "XOF"),))
        self.assertEqual(self.repository.saved, [])
        self.assertIn((event_id, self.use_case.CONSUMER_NAME), self.processed.processed)

    def test_duplicate_event_does_not_add_amount_twice(self):
        event_id = uuid4()
        first = self.execute(event_id=event_id)
        replay = self.execute(event_id=event_id)

        self.assertTrue(first.applied)
        self.assertFalse(replay.applied)
        self.assertEqual(self.contact.order_count, 1)
        self.assertEqual(self.contact.total_spent_by_currency, (Money("25", "XOF"),))
        self.assertEqual(len(self.loyalty_calculator.calculated), 1)

    def test_purchase_history_records_delivery_date_once_per_order(self):
        order_id = uuid4()
        purchase_date = datetime(2026, 9, 22, 14, 30, tzinfo=timezone.utc)
        first = self.execute(order_id=order_id, updated_at=purchase_date)
        replay = self.execute(
            event_id=uuid4(),
            order_id=order_id,
            updated_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )

        self.assertTrue(first.applied)
        self.assertFalse(replay.applied)
        self.assertEqual(self.contact.order_count, 1)
        self.assertEqual(len(self.contact.purchase_history), 1)
        self.assertEqual(self.contact.purchase_history[0].order_id, order_id)
        self.assertEqual(self.contact.purchase_history[0].purchased_at, purchase_date)

    def test_missing_contact_raises_without_processed_marker(self):
        event_id = uuid4()
        self.repository.contact = None

        with self.assertRaises(ResourceNotFoundException):
            self.execute(event_id=event_id)

        self.assertNotIn((event_id, self.use_case.CONSUMER_NAME), self.processed.processed)


if __name__ == "__main__":
    unittest.main()
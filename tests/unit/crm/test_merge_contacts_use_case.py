import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.crm.application.exceptions import (
    ContactAlreadyMergedException,
    ContactsMustBeDistinctException,
    ContactNotFoundException,
)
from contexts.crm.application.merge_contacts_use_case import MergeContactsUseCase
from contexts.crm.application.consume_contact_merged_use_case import (
    ConsumeContactMergedUseCase,
)
from contexts.crm.application.events import ContactMerged, MergedContactSnapshot
from contexts.crm.domain.contact import Contact
from contexts.crm.domain.contact_status import ContactStatus
from contexts.crm.domain.purchase_history_entry import PurchaseHistoryEntry
from shared_kernel.value_objects.money import Money


class InMemoryContactRepository:
    def __init__(self, contacts):
        self.contacts = {contact.id: contact for contact in contacts}
        self.saved = []

    def find_for_update_by_id(self, contact_id):
        return self.contacts.get(contact_id)

    def save(self, contact):
        self.contacts[contact.id] = contact
        self.saved.append(contact.id)


class InMemoryOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class InMemoryUnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


class InMemoryProcessedEvents:
    def __init__(self):
        self.processed = set()

    def has_processed(self, event_id, consumer_name):
        return (event_id, consumer_name) in self.processed

    def mark_processed(self, event_id, consumer_name):
        self.processed.add((event_id, consumer_name))


class MergeContactsUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        occurred_at = datetime(2026, 9, 20, tzinfo=timezone.utc)
        self.primary = Contact.create(
            merchant_id=self.merchant_id,
            platform_connection_id=uuid4(),
            external_identifier="primary-id",
            display_name="Primary",
            initial_total_spent=Money("20", "XOF"),
            occurred_at=occurred_at,
        )
        self.duplicate = Contact.create(
            merchant_id=self.merchant_id,
            platform_connection_id=uuid4(),
            external_identifier="duplicate-id",
            display_name="Duplicate",
            initial_total_spent=Money("30", "USD"),
            occurred_at=occurred_at,
        )
        self.repository = InMemoryContactRepository([self.primary, self.duplicate])
        self.outbox = InMemoryOutbox()
        self.use_case = MergeContactsUseCase(
            contact_repository=self.repository,
            unit_of_work=InMemoryUnitOfWork(),
            outbox=self.outbox,
        )

    def execute(self, primary=None, duplicate=None, merchant_id=None):
        return self.use_case.execute(
            primary_contact_id=primary or self.primary.id,
            duplicate_contact_id=duplicate or self.duplicate.id,
            merchant_id=merchant_id or self.merchant_id,
        )

    def test_marks_only_duplicate_and_publishes_snapshot(self):
        result = self.execute()

        self.assertEqual(result.primary_contact_id, self.primary.id)
        self.assertEqual(result.merged_contact_id, self.duplicate.id)
        self.assertEqual(result.status, "merge_in_progress")
        self.assertEqual(self.primary.status, ContactStatus.ACTIVE)
        self.assertEqual(self.duplicate.status, ContactStatus.MERGED)
        self.assertEqual(self.duplicate.merged_into_contact_id, self.primary.id)
        self.assertEqual(self.repository.saved, [self.duplicate.id])
        self.assertEqual(len(self.outbox.events), 1)
        event = self.outbox.events[0]
        self.assertEqual(event.primary_contact_id, self.primary.id)
        self.assertEqual(event.merged_contact_id, self.duplicate.id)
        self.assertEqual(event.snapshot.total_spent_by_currency, (Money("30", "USD"),))
        self.assertEqual(event.snapshot.order_count, 0)
        self.assertEqual(event.snapshot.purchase_history, ())
        self.assertEqual(event.snapshot.tags, ())

    def test_rejects_contacts_from_different_merchants(self):
        self.duplicate.merchant_id = uuid4()

        with self.assertRaises(ContactNotFoundException):
            self.execute()

        self.assertEqual(self.outbox.events, [])
        self.assertEqual(self.repository.saved, [])

    def test_rejects_contact_already_merged(self):
        self.duplicate.status = ContactStatus.MERGED
        self.duplicate.merged_into_contact_id = uuid4()

        with self.assertRaises(ContactAlreadyMergedException):
            self.execute()

        self.assertEqual(self.outbox.events, [])
        self.assertEqual(self.repository.saved, [])

    def test_rejects_already_merged_primary(self):
        self.primary.status = ContactStatus.MERGED
        self.primary.merged_into_contact_id = uuid4()

        with self.assertRaises(ContactAlreadyMergedException):
            self.execute()

        self.assertEqual(self.outbox.events, [])
        self.assertEqual(self.repository.saved, [])

    def test_rejects_identical_contact_ids(self):
        with self.assertRaises(ContactsMustBeDistinctException):
            self.execute(primary=self.duplicate.id, duplicate=self.duplicate.id)

        self.assertEqual(self.outbox.events, [])
        self.assertEqual(self.repository.saved, [])

    def test_merge_consumer_absorbs_snapshot_once(self):
        purchase = PurchaseHistoryEntry(uuid4(), datetime(2026, 9, 19, tzinfo=timezone.utc))
        event = ContactMerged(
            event_id=uuid4(),
            occurred_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
            merchant_id=self.merchant_id,
            primary_contact_id=self.primary.id,
            merged_contact_id=self.duplicate.id,
            snapshot=MergedContactSnapshot(
                total_spent_by_currency=(Money("30", "XOF"), Money("9.50", "USD")),
                order_count=2,
                purchase_history=(purchase,),
                tags=("vip", "returning"),
            ),
        )
        processed = InMemoryProcessedEvents()
        consumer = ConsumeContactMergedUseCase(
            contact_repository=self.repository,
            processed_events=processed,
            unit_of_work=InMemoryUnitOfWork(),
        )

        first = consumer.execute(event)
        replay = consumer.execute(event)

        totals = {money.currency: money.amount for money in self.primary.total_spent_by_currency}
        self.assertTrue(first.applied)
        self.assertFalse(replay.applied)
        self.assertEqual(totals, {"XOF": Money("20", "XOF").amount + Money("30", "XOF").amount, "USD": Money("9.50", "USD").amount})
        self.assertEqual(self.primary.order_count, 2)
        self.assertEqual(self.primary.purchase_history, (purchase,))
        self.assertEqual(set(self.primary.tags), {"vip", "returning"})
        self.assertEqual(self.repository.saved, [self.primary.id])


if __name__ == "__main__":
    unittest.main()

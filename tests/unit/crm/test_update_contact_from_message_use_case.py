import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.crm.application.update_contact_from_message_use_case import (
    UpdateContactFromMessageUseCase,
)
from contexts.crm.application.exceptions import InvalidContactIdentityException
from contexts.crm.domain.contact import Contact
from contexts.crm.domain.contact_status import ContactStatus
from shared_kernel.value_objects.money import Money


class InMemoryContactRepository:
    def __init__(self):
        self.contacts = {}
        self.saved = []

    @staticmethod
    def _key(merchant_id, platform_connection_id, external_identifier):
        return merchant_id, platform_connection_id, external_identifier

    def find_by_external_identifier(self, merchant_id, platform_connection_id, external_identifier):
        return self.contacts.get(self._key(merchant_id, platform_connection_id, external_identifier))

    def find_for_update_by_external_identifier(self, merchant_id, platform_connection_id, external_identifier):
        return self.find_by_external_identifier(merchant_id, platform_connection_id, external_identifier)

    def find_for_update_by_id(self, contact_id):
        return next((contact for contact in self.contacts.values() if contact.id == contact_id), None)

    def get_or_create(self, contact):
        key = self._key(contact.merchant_id, contact.platform_connection_id, contact.external_identifier)
        existing = self.contacts.get(key)
        if existing is not None:
            return existing, False
        self.contacts[key] = contact
        return contact, True

    def save(self, contact):
        key = self._key(contact.merchant_id, contact.platform_connection_id, contact.external_identifier)
        self.contacts[key] = contact
        self.saved.append(contact)


class FixedDefaultsProvider:
    def __init__(self):
        self.calls = []

    def initial_total_spent(self, merchant_id):
        self.calls.append(merchant_id)
        return Money("0", "XOF")


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
        self.exited = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.exited += 1
        return False


class UpdateContactFromMessageUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.connection_id = uuid4()
        self.repository = InMemoryContactRepository()
        self.defaults = FixedDefaultsProvider()
        self.processed = InMemoryProcessedMessages()
        self.unit_of_work = InMemoryUnitOfWork()
        self.use_case = UpdateContactFromMessageUseCase(
            contact_repository=self.repository,
            defaults_provider=self.defaults,
            processed_messages=self.processed,
            unit_of_work=self.unit_of_work,
        )

    def execute(self, event_id, connection_id=None, external_identifier="platform-user", display_name="Ari", timestamp=None):
        return self.use_case.execute(
            event_id=event_id,
            merchant_id=self.merchant_id,
            platform_connection_id=connection_id or self.connection_id,
            external_identifier=external_identifier,
            display_name=display_name,
            timestamp=timestamp or datetime(2026, 9, 20, tzinfo=timezone.utc),
        )

    def test_creates_contact_with_merchant_currency_defaults(self):
        event_id = uuid4()
        result = self.execute(event_id)

        contact = next(iter(self.repository.contacts.values()))
        self.assertTrue(result.is_new_contact)
        self.assertEqual(contact.display_name, "Ari")
        self.assertEqual(contact.total_spent_by_currency, (Money("0", "XOF"),))
        self.assertEqual(contact.order_count, 0)
        self.assertEqual(self.defaults.calls, [self.merchant_id])
        self.assertIn((event_id, self.use_case.CONSUMER_NAME), self.processed.processed)

    def test_display_name_change_updates_contact_without_creating_duplicate(self):
        first = self.execute(uuid4(), display_name="Ari")
        second = self.execute(
            uuid4(),
            display_name="Ari New",
            timestamp=datetime(2026, 9, 21, tzinfo=timezone.utc),
        )

        contact = next(iter(self.repository.contacts.values()))
        self.assertTrue(first.is_new_contact)
        self.assertFalse(second.is_new_contact)
        self.assertEqual(first.contact_id, second.contact_id)
        self.assertEqual(len(self.repository.contacts), 1)
        self.assertEqual(contact.display_name, "Ari New")
        self.assertEqual(contact.order_count, 0)
        self.assertEqual(contact.total_spent_by_currency, (Money("0", "XOF"),))
        self.assertEqual(len(self.defaults.calls), 1)

    def test_older_message_does_not_rewind_name_or_last_interaction(self):
        self.execute(uuid4(), display_name="Current", timestamp=datetime(2026, 9, 22, tzinfo=timezone.utc))
        self.execute(uuid4(), display_name="Stale", timestamp=datetime(2026, 9, 20, tzinfo=timezone.utc))

        contact = next(iter(self.repository.contacts.values()))
        self.assertEqual(contact.display_name, "Current")
        self.assertEqual(contact.last_interaction_at, datetime(2026, 9, 22, tzinfo=timezone.utc))

    def test_same_external_identifier_on_another_connection_is_not_merged(self):
        first = self.execute(uuid4(), connection_id=self.connection_id)
        second = self.execute(uuid4(), connection_id=uuid4())

        self.assertNotEqual(first.contact_id, second.contact_id)
        self.assertEqual(len(self.repository.contacts), 2)

    def test_duplicate_event_is_idempotent(self):
        event_id = uuid4()
        first = self.execute(event_id, display_name="First")
        duplicate = self.execute(
            event_id,
            display_name="Should not apply",
            timestamp=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )

        contact = next(iter(self.repository.contacts.values()))
        self.assertEqual(first.contact_id, duplicate.contact_id)
        self.assertFalse(duplicate.is_new_contact)
        self.assertEqual(contact.display_name, "First")
        self.assertEqual(contact.last_interaction_at, datetime(2026, 9, 20, tzinfo=timezone.utc))

    def test_blank_external_identifier_is_rejected_before_transaction(self):
        with self.assertRaises(InvalidContactIdentityException):
            self.execute(uuid4(), external_identifier="   ")

        self.assertEqual(self.unit_of_work.entered, 0)
        self.assertEqual(self.repository.contacts, {})

    def test_message_for_merged_external_identity_redirects_to_primary(self):
        timestamp = datetime(2026, 9, 20, tzinfo=timezone.utc)
        primary = Contact.create(
            merchant_id=self.merchant_id,
            platform_connection_id=self.connection_id,
            external_identifier="primary-platform-id",
            display_name="Primary",
            initial_total_spent=Money("0", "XOF"),
            occurred_at=timestamp,
        )
        duplicate = Contact.create(
            merchant_id=self.merchant_id,
            platform_connection_id=self.connection_id,
            external_identifier="duplicate-platform-id",
            display_name="Duplicate",
            initial_total_spent=Money("0", "XOF"),
            occurred_at=timestamp,
        )
        duplicate.mark_merged(primary.id)
        self.repository.contacts[
            self.repository._key(self.merchant_id, self.connection_id, primary.external_identifier)
        ] = primary
        self.repository.contacts[
            self.repository._key(self.merchant_id, self.connection_id, duplicate.external_identifier)
        ] = duplicate

        result = self.execute(
            uuid4(),
            connection_id=self.connection_id,
            external_identifier=duplicate.external_identifier,
            display_name="Redirected Name",
            timestamp=datetime(2026, 9, 21, tzinfo=timezone.utc),
        )

        self.assertEqual(result.contact_id, primary.id)
        self.assertFalse(result.is_new_contact)
        self.assertEqual(primary.display_name, "Redirected Name")
        self.assertEqual(primary.last_interaction_at, datetime(2026, 9, 21, tzinfo=timezone.utc))
        self.assertEqual(duplicate.status, ContactStatus.MERGED)
        self.assertEqual(duplicate.display_name, "Duplicate")


if __name__ == "__main__":
    unittest.main()
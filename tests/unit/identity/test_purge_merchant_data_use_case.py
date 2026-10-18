import unittest
from uuid import uuid4

from contexts.identity.application.use_cases.purge_merchant_data_use_case import (
    PurgeMerchantDataUseCase,
)
from contexts.identity.domain.events.identity_events import MerchantDataPurged


class FakeMerchants:
    def __init__(self):
        self.deleted = []

    def delete_by_id(self, merchant_id):
        self.deleted.append(merchant_id)


class FakeProcessedEvents:
    def __init__(self):
        self.events = set()

    def has_processed(self, event_id, consumer_name):
        return (event_id, consumer_name) in self.events

    def mark_processed(self, event_id, consumer_name):
        self.events.add((event_id, consumer_name))


class FakeUnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


class FakeOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class PurgeMerchantDataUseCaseTests(unittest.TestCase):
    def test_deletes_merchant_once_and_emits_completion(self):
        merchants = FakeMerchants()
        processed_events = FakeProcessedEvents()
        outbox = FakeOutbox()
        use_case = PurgeMerchantDataUseCase(
            merchants, processed_events, FakeUnitOfWork(), outbox
        )
        event_id = uuid4()
        merchant_id = uuid4()

        self.assertTrue(use_case.execute(event_id, merchant_id))
        self.assertFalse(use_case.execute(event_id, merchant_id))

        self.assertEqual(merchants.deleted, [merchant_id])
        self.assertEqual(len(outbox.events), 1)
        self.assertIsInstance(outbox.events[0], MerchantDataPurged)
        self.assertEqual(outbox.events[0].context, "identity")
        self.assertEqual(outbox.events[0].merchant_id, merchant_id)


if __name__ == "__main__":
    unittest.main()
import unittest
from uuid import uuid4

from contexts.rules_engine.application.use_cases.purge_merchant_data_use_case import (
    PurgeMerchantDataUseCase,
)
from contexts.rules_engine.domain.events.merchant_data_purged import MerchantDataPurged


class FakePurger:
    def __init__(self):
        self.calls = []

    def purge_merchant_rule_sets(self, event_id, merchant_id):
        self.calls.append((event_id, merchant_id))


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
    def test_purge_is_idempotent_and_publishes_one_completion(self):
        purger = FakePurger()
        outbox = FakeOutbox()
        use_case = PurgeMerchantDataUseCase(
            purger, FakeProcessedEvents(), FakeUnitOfWork(), outbox
        )
        event_id = uuid4()
        merchant_id = uuid4()

        self.assertTrue(use_case.execute(event_id, merchant_id))
        self.assertFalse(use_case.execute(event_id, merchant_id))

        self.assertEqual(purger.calls, [(event_id, merchant_id)])
        self.assertEqual(len(outbox.events), 1)
        self.assertIsInstance(outbox.events[0], MerchantDataPurged)
        self.assertEqual(outbox.events[0].context, "rules-engine")


if __name__ == "__main__":
    unittest.main()
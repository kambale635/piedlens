import unittest
from uuid import uuid4

from contexts.payments.application.use_cases.consume_payment_succeeded_use_case import ConsumePaymentSucceededUseCase


class Processed:
    def __init__(self): self.events = set()
    def has_processed(self, event_id, consumer_name): return (event_id, consumer_name) in self.events
    def mark_processed(self, event_id, consumer_name): self.events.add((event_id, consumer_name))


class Uow:
    def __init__(self): self.entries = 0
    def __enter__(self): self.entries += 1; return self
    def __exit__(self, *args): return False


class ChangePlan:
    def __init__(self): self.calls = []
    def change_in_current_transaction(self, merchant_id, plan_code): self.calls.append((merchant_id, plan_code))


class ConsumePaymentSucceededTests(unittest.TestCase):
    def test_payment_event_replay_changes_plan_once(self):
        processed, uow, change = Processed(), Uow(), ChangePlan()
        use_case = ConsumePaymentSucceededUseCase(processed, uow, change)
        event_id, merchant_id = uuid4(), uuid4()
        first = use_case.execute(event_id, merchant_id, "pro")
        replay = use_case.execute(event_id, merchant_id, "pro")
        self.assertEqual(first["outcome"], "plan_changed")
        self.assertEqual(replay["outcome"], "already_processed")
        self.assertEqual(change.calls, [(merchant_id, "pro")])
        self.assertEqual(uow.entries, 2)


if __name__ == "__main__":
    unittest.main()

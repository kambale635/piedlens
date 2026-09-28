import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.order_detection.application.events import (
    ReminderCancelled,
    ReminderDeliveryFailed,
    ReminderProposed,
    ReminderSent,
)
from contexts.order_detection.application.reminder_delivery import (
    ReminderDeliveryMode,
    ReminderDeliveryResult,
)
from contexts.order_detection.application.send_scheduled_reminders_use_case import (
    SendScheduledRemindersUseCase,
)
from contexts.order_detection.domain.order import Order
from contexts.order_detection.domain.order_status import OrderStatus
from contexts.order_detection.domain.reminder import Reminder, ReminderStatus, ReminderType
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class InMemoryOrderRepository:
    def __init__(self, orders):
        self.orders = {order.id: order for order in orders}

    def find_by_id(self, order_id):
        return self.orders.get(order_id)

    def save(self, order):
        self.orders[order.id] = order

    def find_pending_by_contact(self, contact_id, within_days):
        return []

    def find_by_source_candidate_id(self, candidate_id):
        return None


class InMemoryReminderRepository:
    def __init__(self, reminders):
        self.reminders = {reminder.id: reminder for reminder in reminders}

    def has_scheduled(self, order_id, reminder_type):
        return False

    def find_by_id(self, reminder_id):
        return self.reminders.get(reminder_id)

    def save(self, reminder):
        self.reminders[reminder.id] = reminder

    def claim_due(self, now, lease_until, limit):
        claimed = []
        for reminder in self.reminders.values():
            due_scheduled = (
                reminder.status is ReminderStatus.SCHEDULED
                and reminder.scheduled_for <= now
                and (reminder.next_attempt_at is None or reminder.next_attempt_at <= now)
            )
            expired_processing = (
                reminder.status is ReminderStatus.PROCESSING
                and reminder.lease_until is not None
                and reminder.lease_until <= now
            )
            if due_scheduled or expired_processing:
                reminder.claim(lease_until)
                claimed.append(reminder)
                if len(claimed) >= limit:
                    break
        return claimed


class InMemoryProcessedEvents:
    def __init__(self):
        self.events = set()

    def has_processed(self, event_id, consumer_name):
        return (event_id, consumer_name) in self.events

    def mark_processed(self, event_id, consumer_name):
        self.events.add((event_id, consumer_name))


class InMemoryUnitOfWork:
    def __init__(self, reminders):
        self.reminders = reminders

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def lock_order(self, order_id):
        pass

    def lock_reminder(self, reminder_id):
        pass


class FixedClock:
    def __init__(self):
        self.instant = datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc)

    def now(self):
        return self.instant


class FixedDeliveryPolicy:
    def __init__(self, mode):
        self.mode = mode

    def mode_for(self, order):
        return self.mode


class FixedMessageProvider:
    def render(self, reminder, order):
        return f"Configured message for {order.id}"


class RecordingDelivery:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def send(self, merchant_id, contact_id, content, idempotency_key):
        self.calls.append((merchant_id, contact_id, content, idempotency_key))
        return self.outcomes.pop(0)


class FixedRetryPolicy:
    def next_attempt_at(self, attempt_count, failed_at):
        return failed_at + timedelta(minutes=2 ** attempt_count)


class InMemoryOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class SendScheduledRemindersUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.order = Order.detect(
            merchant_id=uuid4(),
            contact_id=uuid4(),
            detected_amount=Money("60", "USD"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
        )
        self.reminder = Reminder.schedule(
            order_id=self.order.id,
            reminder_type=ReminderType.PAYMENT_PENDING,
            scheduled_for=datetime(2026, 9, 27, 13, 0, tzinfo=timezone.utc),
            custom_message=None,
        )
        self.clock = FixedClock()
        self.reminder_repository = InMemoryReminderRepository([self.reminder])
        self.order_repository = InMemoryOrderRepository([self.order])
        self.processed_events = InMemoryProcessedEvents()
        self.delivery = RecordingDelivery([ReminderDeliveryResult(succeeded=True)])
        self.outbox = InMemoryOutbox()

    def make_use_case(self, mode, delivery=None):
        return SendScheduledRemindersUseCase(
            order_repository=self.order_repository,
            reminder_repository=self.reminder_repository,
            processed_events=self.processed_events,
            delivery_policy=FixedDeliveryPolicy(mode),
            message_provider=FixedMessageProvider(),
            delivery=delivery or self.delivery,
            retry_policy=FixedRetryPolicy(),
            unit_of_work=InMemoryUnitOfWork(self.reminder_repository),
            outbox=self.outbox,
            clock=self.clock,
            batch_limit=10,
            lease_duration=timedelta(minutes=5),
        )

    def test_automatic_success_is_idempotent_and_marks_processed(self):
        result = self.make_use_case(ReminderDeliveryMode.AUTOMATIC_SEND).execute()

        self.assertEqual((result.sent_count, result.proposed_count, result.failed_count), (1, 0, 0))
        self.assertEqual(self.reminder.status, ReminderStatus.SENT)
        self.assertEqual(self.delivery.calls[0][3], self.reminder.id)
        self.assertIn(
            (self.reminder.id, SendScheduledRemindersUseCase.CONSUMER_NAME),
            self.processed_events.events,
        )
        self.assertIsInstance(self.outbox.events[0], ReminderSent)

    def test_manual_plan_proposes_without_sending(self):
        result = self.make_use_case(ReminderDeliveryMode.MANUAL_PROPOSAL).execute()

        self.assertEqual((result.sent_count, result.proposed_count, result.failed_count), (0, 1, 0))
        self.assertEqual(self.reminder.status, ReminderStatus.PROPOSED)
        self.assertEqual(self.delivery.calls, [])
        self.assertIsInstance(self.outbox.events[0], ReminderProposed)

    def test_failed_send_is_rescheduled_and_not_marked_processed(self):
        failing_delivery = RecordingDelivery(
            [ReminderDeliveryResult(succeeded=False, failure_code="TEMPORARY_FAILURE")]
        )
        result = self.make_use_case(
            ReminderDeliveryMode.AUTOMATIC_SEND,
            delivery=failing_delivery,
        ).execute()

        self.assertEqual((result.sent_count, result.proposed_count, result.failed_count), (0, 0, 1))
        self.assertEqual(self.reminder.status, ReminderStatus.SCHEDULED)
        self.assertEqual(self.reminder.attempt_count, 1)
        self.assertEqual(self.reminder.next_attempt_at, self.clock.instant + timedelta(minutes=2))
        self.assertFalse(self.processed_events.events)
        self.assertIsInstance(self.outbox.events[0], ReminderDeliveryFailed)

    def test_closed_order_cancels_reminder_without_sending(self):
        self.order.change_status(OrderStatus.PAID_NOT_DELIVERED)
        result = self.make_use_case(ReminderDeliveryMode.AUTOMATIC_SEND).execute()

        self.assertEqual((result.sent_count, result.proposed_count, result.failed_count), (0, 0, 0))
        self.assertEqual(self.reminder.status, ReminderStatus.CANCELLED)
        self.assertEqual(self.delivery.calls, [])
        self.assertIsInstance(self.outbox.events[0], ReminderCancelled)

    def test_expired_processing_lease_is_reclaimed_with_new_token(self):
        self.reminder.claim(self.clock.instant - timedelta(seconds=1))
        old_lease_token = self.reminder.lease_token

        self.make_use_case(ReminderDeliveryMode.AUTOMATIC_SEND).execute()

        self.assertEqual(self.reminder.status, ReminderStatus.SENT)
        self.assertNotEqual(old_lease_token, self.reminder.lease_token)

    def test_worker_cannot_finalize_after_its_lease_expires(self):
        class SlowDelivery(RecordingDelivery):
            def send(inner_self, merchant_id, contact_id, content, idempotency_key):
                self.clock.instant += timedelta(minutes=6)
                return super(SlowDelivery, inner_self).send(
                    merchant_id,
                    contact_id,
                    content,
                    idempotency_key,
                )

        result = self.make_use_case(
            ReminderDeliveryMode.AUTOMATIC_SEND,
            delivery=SlowDelivery([ReminderDeliveryResult(succeeded=True)]),
        ).execute()

        self.assertEqual((result.sent_count, result.failed_count), (0, 0))
        self.assertEqual(self.reminder.status, ReminderStatus.PROCESSING)
        self.assertEqual(self.outbox.events, [])


if __name__ == "__main__":
    unittest.main()
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.order_detection.application.events import ReminderScheduled
from contexts.order_detection.application.reminder_exceptions import (
    ReminderAlreadyScheduledException,
)
from contexts.order_detection.application.schedule_reminder_use_case import (
    ScheduleReminderUseCase,
)
from contexts.order_detection.domain.order import Order
from contexts.order_detection.domain.order_status import OrderStatus
from contexts.order_detection.domain.reminder import ReminderType
from shared_kernel.application_exceptions import ResourceNotFoundException, ValidationException
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class InMemoryOrderRepository:
    def __init__(self, order):
        self.order = order
        self.locked_order_ids = []

    def find_by_id(self, order_id):
        return self.order if self.order and self.order.id == order_id else None

    def save(self, order):
        raise AssertionError("ScheduleReminderUseCase must not modify Order.")

    def find_pending_by_contact(self, contact_id, within_days):
        return []

    def find_by_source_candidate_id(self, candidate_id):
        return None


class InMemoryReminderRepository:
    def __init__(self):
        self.scheduled = set()
        self.saved = []

    def has_scheduled(self, order_id, reminder_type):
        return (order_id, reminder_type) in self.scheduled

    def save(self, reminder):
        self.saved.append(reminder)
        self.scheduled.add((reminder.order_id, reminder.reminder_type))


class FixedReminderPolicy:
    def __init__(self, delay):
        self.delay = delay
        self.requested = None

    def delay_for(self, order, reminder_type):
        self.requested = (order.id, reminder_type)
        return self.delay


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

    def lock_order(self, order_id):
        pass


class FixedClock:
    def __init__(self):
        self.instant = datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc)

    def now(self):
        return self.instant


class InMemoryOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class ScheduleReminderUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.order = Order.detect(
            merchant_id=uuid4(),
            contact_id=uuid4(),
            detected_amount=Money("45", "USD"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
        )
        self.order_repository = InMemoryOrderRepository(self.order)
        self.reminder_repository = InMemoryReminderRepository()
        self.policy = FixedReminderPolicy(timedelta(hours=36))
        self.unit_of_work = InMemoryUnitOfWork()
        self.clock = FixedClock()
        self.outbox = InMemoryOutbox()
        self.use_case = ScheduleReminderUseCase(
            order_repository=self.order_repository,
            reminder_repository=self.reminder_repository,
            policy_provider=self.policy,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
            clock=self.clock,
        )

    def test_schedules_from_injected_policy_and_appends_outbox_event(self):
        result = self.use_case.execute(
            order_id=self.order.id,
            reminder_type="payment_pending",
            custom_message="Follow up",
        )

        self.assertEqual(result.scheduled_for, self.clock.instant + timedelta(hours=36))
        self.assertEqual(len(self.reminder_repository.saved), 1)
        reminder = self.reminder_repository.saved[0]
        self.assertEqual(reminder.custom_message, "Follow up")
        self.assertEqual(self.policy.requested, (self.order.id, ReminderType.PAYMENT_PENDING))
        self.assertIsInstance(self.outbox.events[0], ReminderScheduled)
        self.assertEqual(self.unit_of_work.entered, 1)
        self.assertEqual(self.unit_of_work.exited, 1)

    def test_refuses_duplicate_scheduled_reminder(self):
        self.reminder_repository.scheduled.add((self.order.id, ReminderType.PAYMENT_PENDING))

        with self.assertRaises(ReminderAlreadyScheduledException):
            self.use_case.execute(self.order.id, "payment_pending")

        self.assertEqual(self.reminder_repository.saved, [])
        self.assertEqual(self.outbox.events, [])

    def test_rejects_type_that_does_not_apply_to_order_status(self):
        with self.assertRaises(ValidationException):
            self.use_case.execute(self.order.id, "delivery_pending")

        self.assertEqual(self.reminder_repository.saved, [])
        self.assertEqual(self.outbox.events, [])

    def test_rejects_unknown_type_and_non_positive_configured_delay(self):
        with self.assertRaises(ValidationException):
            self.use_case.execute(self.order.id, "unknown")

        self.policy.delay = timedelta(0)
        with self.assertRaises(ValidationException):
            self.use_case.execute(self.order.id, "payment_pending")

        self.assertEqual(self.reminder_repository.saved, [])

    def test_missing_order_is_not_found(self):
        self.order_repository.order = None

        with self.assertRaises(ResourceNotFoundException):
            self.use_case.execute(uuid4(), "payment_pending")

        self.assertEqual(self.reminder_repository.saved, [])

    def test_delivery_reminder_requires_paid_not_delivered_status(self):
        self.order.change_status(OrderStatus.PAID_NOT_DELIVERED)

        result = self.use_case.execute(self.order.id, "delivery_pending")

        self.assertEqual(result.scheduled_for, self.clock.instant + timedelta(hours=36))
        self.assertEqual(self.reminder_repository.saved[0].reminder_type, ReminderType.DELIVERY_PENDING)


if __name__ == "__main__":
    unittest.main()
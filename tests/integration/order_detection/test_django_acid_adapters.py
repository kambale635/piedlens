from datetime import datetime, timezone
from uuid import uuid4

from django.test import TransactionTestCase

from contexts.order_detection.application.create_order_from_promoted_detection_use_case import (
    CreateOrderFromPromotedDetectionUseCase,
)
from contexts.order_detection.application.get_dormant_money_dashboard_use_case import (
    GetDormantMoneyDashboardUseCase,
)
from contexts.order_detection.application.list_pending_detection_candidates_use_case import (
    ListPendingDetectionCandidatesUseCase,
)
from contexts.order_detection.application.reminder_exceptions import (
    ReminderAlreadyScheduledException,
)
from contexts.order_detection.application.schedule_reminder_use_case import (
    ScheduleReminderUseCase,
)
from contexts.order_detection.application.reminder_delivery import (
    ReminderDeliveryMode,
    ReminderDeliveryResult,
)
from contexts.order_detection.application.send_scheduled_reminders_use_case import (
    SendScheduledRemindersUseCase,
)
from contexts.order_detection.application.events import DetectionCandidatePromoted
from contexts.order_detection.application.validate_or_reject_detection_use_case import (
    ValidateOrRejectDetectionUseCase,
)
from contexts.order_detection.application.update_order_status_use_case import (
    UpdateOrderStatusUseCase,
)
from contexts.order_detection.domain.detection_candidate import DetectionCandidate
from contexts.order_detection.domain.reminder import Reminder, ReminderType
from contexts.order_detection.infrastructure.django_detection_candidate_repository import (
    DjangoDetectionCandidateRepository,
)
from contexts.order_detection.infrastructure.django_order_detection_outbox import (
    DjangoOrderDetectionOutbox,
)
from contexts.order_detection.infrastructure.django_order_repository import (
    DjangoOrderRepository,
)
from contexts.order_detection.infrastructure.django_processed_event_repository import (
    DjangoProcessedEventRepository,
)
from contexts.order_detection.infrastructure.django_unit_of_work import (
    DjangoOrderDetectionUnitOfWork,
)
from contexts.order_detection.infrastructure.system_clock import SystemClock
from contexts.order_detection.infrastructure.models import (
    OrderRecord,
    OutboxEventRecord,
    ProcessedEventRecord,
    DetectionCandidateRecord,
    ReminderRecord,
)
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class DjangoOrderDetectionAcidTests(TransactionTestCase):
    """Exercise real ORM adapters and transaction rollback/commit behavior."""

    reset_sequences = True

    def setUp(self):
        self.event = DetectionCandidatePromoted(
            candidate_id=uuid4(),
            merchant_id=uuid4(),
            contact_id=uuid4(),
            source_message_id=uuid4(),
            detected_amount=Money("75.25", "USD"),
            confidence_score=ConfidenceScore(62),
            matched_rule_ids=(uuid4(),),
            event_id=uuid4(),
            occurred_at=datetime.now(timezone.utc),
        )
        self.order_repository = DjangoOrderRepository()
        self.processed_events = DjangoProcessedEventRepository()
        self.outbox = DjangoOrderDetectionOutbox()
        self.unit_of_work = DjangoOrderDetectionUnitOfWork()
        self.use_case = CreateOrderFromPromotedDetectionUseCase(
            order_repository=self.order_repository,
            processed_events=self.processed_events,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
        )

    def test_consumer_commits_order_outbox_and_processed_marker_together(self):
        result = self.use_case.execute(self.event)

        self.assertTrue(result.created)
        self.assertEqual(OrderRecord.objects.count(), 1)
        self.assertEqual(OutboxEventRecord.objects.count(), 1)
        self.assertEqual(ProcessedEventRecord.objects.count(), 1)

    def test_exception_rolls_back_order_outbox_and_processed_marker(self):
        with self.assertRaises(RuntimeError):
            with self.unit_of_work:
                order = self._make_order()
                self.order_repository.save(order)
                self.outbox.add(self._make_order_detected_event(order))
                self.processed_events.mark_processed(
                    self.event.event_id,
                    self.use_case.CONSUMER_NAME,
                )
                raise RuntimeError("force rollback")

        self.assertEqual(OrderRecord.objects.count(), 0)
        self.assertEqual(OutboxEventRecord.objects.count(), 0)
        self.assertEqual(ProcessedEventRecord.objects.count(), 0)

    def test_same_promotion_delivered_twice_creates_one_order_and_outbox_event(self):
        first = self.use_case.execute(self.event)
        second = self.use_case.execute(self.event)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.order_id, second.order_id)
        self.assertEqual(OrderRecord.objects.count(), 1)
        self.assertEqual(OutboxEventRecord.objects.count(), 1)
        self.assertEqual(ProcessedEventRecord.objects.count(), 1)

    def test_candidate_decision_and_outbox_roll_back_together(self):
        candidate = DetectionCandidate.create(
            merchant_id=uuid4(),
            contact_id=uuid4(),
            detected_amount=Money("25.00", "USD"),
            confidence_score=ConfidenceScore(55),
            source_message_id=uuid4(),
            matched_rule_ids=(uuid4(),),
        )
        candidate_repository = DjangoDetectionCandidateRepository()
        with self.unit_of_work:
            candidate_repository.save(candidate)

        class FailingOutbox:
            def add(inner_self, event):
                self.outbox.add(event)
                raise RuntimeError("force outbox failure")

        use_case = ValidateOrRejectDetectionUseCase(
            candidate_repository=candidate_repository,
            unit_of_work=self.unit_of_work,
            outbox=FailingOutbox(),
        )

        with self.assertRaises(RuntimeError):
            use_case.execute(
                candidate_id=candidate.id,
                decision="validate",
                merchant_id=candidate.merchant_id,
            )

        persisted_candidate = DetectionCandidateRecord.objects.get(id=candidate.id)
        self.assertEqual(persisted_candidate.status, "pending_review")
        self.assertEqual(OutboxEventRecord.objects.count(), 0)
        self.assertEqual(OrderRecord.objects.count(), 0)

    def test_status_transition_locks_order_and_commits_status_with_outbox(self):
        order = self._make_order()
        with self.unit_of_work:
            self.order_repository.save(order)

        use_case = UpdateOrderStatusUseCase(
            order_repository=self.order_repository,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
            clock=SystemClock(),
        )
        result = use_case.execute(
            order_id=order.id,
            new_status="paid_not_delivered",
            triggered_by="system",
        )

        persisted_order = OrderRecord.objects.get(id=order.id)
        event_record = OutboxEventRecord.objects.get()
        self.assertEqual(result.status, "paid_not_delivered")
        self.assertEqual(persisted_order.status, "paid_not_delivered")
        self.assertEqual(event_record.event_type, "OrderStatusChanged")
        self.assertEqual(event_record.payload["previous_status"], "pending_payment")

    def test_dormant_dashboard_filters_by_merchant_age_and_open_status(self):
        from datetime import timedelta

        from contexts.order_detection.domain.order import Order
        from contexts.order_detection.domain.order_status import OrderStatus

        now = datetime.now(timezone.utc)
        older_order = Order.detect(
            merchant_id=self.event.merchant_id,
            contact_id=uuid4(),
            detected_amount=Money("120.00", "USD"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
            occurred_at=now - timedelta(hours=72),
        )
        another_currency_order = Order.detect(
            merchant_id=self.event.merchant_id,
            contact_id=uuid4(),
            detected_amount=Money("5000", "XOF"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
            occurred_at=now - timedelta(hours=48),
        )
        too_recent_order = Order.detect(
            merchant_id=self.event.merchant_id,
            contact_id=uuid4(),
            detected_amount=Money("30.00", "USD"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
            occurred_at=now - timedelta(hours=12),
        )
        cancelled_order = Order.detect(
            merchant_id=self.event.merchant_id,
            contact_id=uuid4(),
            detected_amount=Money("45.00", "USD"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
            occurred_at=now - timedelta(hours=72),
        )
        cancelled_order.change_status(OrderStatus.CANCELLED)
        other_merchant_order = Order.detect(
            merchant_id=uuid4(),
            contact_id=uuid4(),
            detected_amount=Money("1000", "XOF"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
            occurred_at=now - timedelta(hours=72),
        )

        with self.unit_of_work:
            for order in (
                older_order,
                another_currency_order,
                too_recent_order,
                cancelled_order,
                other_merchant_order,
            ):
                self.order_repository.save(order)

        result = GetDormantMoneyDashboardUseCase(self.order_repository).execute(
            self.event.merchant_id,
            older_than_hours=24,
        )

        totals = {money.currency: money.amount for money in result.totals_by_currency}
        self.assertEqual(totals, {"USD": Money("120.00", "USD").amount, "XOF": Money("5000", "XOF").amount})
        self.assertEqual(len(result.orders), 2)
        self.assertEqual(result.orders[0].order_id, older_order.id)

    def test_reminder_and_outbox_commit_once_and_database_blocks_duplicate(self):
        from datetime import timedelta

        from contexts.order_detection.domain.reminder import ReminderType
        from contexts.order_detection.infrastructure.django_reminder_repository import (
            DjangoReminderRepository,
        )

        order = self._make_order()
        with self.unit_of_work:
            self.order_repository.save(order)

        class FixedPolicy:
            def delay_for(self, policy_order, reminder_type):
                return timedelta(hours=24)

        use_case = ScheduleReminderUseCase(
            order_repository=self.order_repository,
            reminder_repository=DjangoReminderRepository(),
            policy_provider=FixedPolicy(),
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
            clock=SystemClock(),
        )

        result = use_case.execute(order.id, "payment_pending")

        self.assertEqual(ReminderRecord.objects.count(), 1)
        self.assertEqual(OutboxEventRecord.objects.filter(event_type="ReminderScheduled").count(), 1)
        self.assertGreater(result.scheduled_for, order.created_at)

        with self.assertRaises(ReminderAlreadyScheduledException):
            use_case.execute(order.id, ReminderType.PAYMENT_PENDING.value)

        self.assertEqual(ReminderRecord.objects.count(), 1)
        self.assertEqual(OutboxEventRecord.objects.filter(event_type="ReminderScheduled").count(), 1)

    def test_scheduled_worker_claims_and_commits_sent_marker_and_outbox(self):
        from datetime import timedelta

        from contexts.order_detection.infrastructure.django_reminder_repository import (
            DjangoReminderRepository,
        )

        order = self._make_order()
        reminder = Reminder.schedule(
            order_id=order.id,
            reminder_type=ReminderType.PAYMENT_PENDING,
            scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=2),
            custom_message="Reminder body",
        )
        with self.unit_of_work:
            self.order_repository.save(order)
            DjangoReminderRepository().save(reminder)

        class AutomaticPolicy:
            def mode_for(self, policy_order):
                return ReminderDeliveryMode.AUTOMATIC_SEND

        class MessageProvider:
            def render(self, policy_reminder, policy_order):
                return "unused custom body"

        class Delivery:
            def __init__(self):
                self.idempotency_keys = []

            def send(self, merchant_id, contact_id, content, idempotency_key):
                self.idempotency_keys.append(idempotency_key)
                return ReminderDeliveryResult(succeeded=True)

        class RetryPolicy:
            def next_attempt_at(self, attempt_count, failed_at):
                return failed_at + timedelta(minutes=5)

        delivery = Delivery()
        worker = SendScheduledRemindersUseCase(
            order_repository=self.order_repository,
            reminder_repository=DjangoReminderRepository(),
            processed_events=self.processed_events,
            delivery_policy=AutomaticPolicy(),
            message_provider=MessageProvider(),
            delivery=delivery,
            retry_policy=RetryPolicy(),
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
            clock=SystemClock(),
            batch_limit=10,
            lease_duration=timedelta(minutes=5),
        )

        result = worker.execute()

        persisted = ReminderRecord.objects.get(id=reminder.id)
        self.assertEqual((result.sent_count, result.proposed_count, result.failed_count), (1, 0, 0))
        self.assertEqual(persisted.status, "sent")
        self.assertIsNone(persisted.lease_token)
        self.assertEqual(delivery.idempotency_keys, [reminder.id])
        self.assertEqual(
            ProcessedEventRecord.objects.filter(
                event_id=reminder.id,
                consumer_name=worker.CONSUMER_NAME,
            ).count(),
            1,
        )
        self.assertEqual(OutboxEventRecord.objects.filter(event_type="ReminderSent").count(), 1)

    def test_expired_processing_reminder_is_claimed_by_database_adapter(self):
        from datetime import timedelta

        from contexts.order_detection.infrastructure.django_reminder_repository import (
            DjangoReminderRepository,
        )

        order = self._make_order()
        reminder = Reminder.schedule(
            order_id=order.id,
            reminder_type=ReminderType.PAYMENT_PENDING,
            scheduled_for=datetime.now(timezone.utc) - timedelta(hours=1),
            custom_message=None,
        )
        old_expiry = datetime.now(timezone.utc) - timedelta(minutes=1)
        reminder.claim(old_expiry)
        with self.unit_of_work:
            self.order_repository.save(order)
            DjangoReminderRepository().save(reminder)

        now = datetime.now(timezone.utc)
        claimed = DjangoReminderRepository().claim_due(
            now=now,
            lease_until=now + timedelta(minutes=5),
            limit=10,
        )

        self.assertEqual([item.id for item in claimed], [reminder.id])
        self.assertNotEqual(claimed[0].lease_token, reminder.lease_token)
        persisted = ReminderRecord.objects.get(id=reminder.id)
        self.assertEqual(persisted.status, "processing")
        self.assertGreater(persisted.lease_until, now)

    def test_pending_candidate_listing_is_merchant_scoped_and_paginated(self):
        from datetime import timedelta

        from contexts.order_detection.infrastructure.django_detection_candidate_repository import (
            DjangoDetectionCandidateRepository,
        )

        base_time = datetime(2026, 9, 20, tzinfo=timezone.utc)
        candidates = [
            DetectionCandidate.create(
                merchant_id=self.event.merchant_id,
                contact_id=uuid4(),
                detected_amount=Money(f"{10 + index}.00", "USD"),
                confidence_score=ConfidenceScore(55 + index),
                source_message_id=uuid4(),
                occurred_at=base_time + timedelta(hours=index),
            )
            for index in range(3)
        ]
        rejected = DetectionCandidate.create(
            merchant_id=self.event.merchant_id,
            contact_id=uuid4(),
            detected_amount=Money("99.00", "USD"),
            confidence_score=ConfidenceScore(40),
            source_message_id=uuid4(),
            occurred_at=base_time,
        )
        rejected.reject()
        other_merchant = DetectionCandidate.create(
            merchant_id=uuid4(),
            contact_id=uuid4(),
            detected_amount=Money("77.00", "USD"),
            confidence_score=ConfidenceScore(45),
            source_message_id=uuid4(),
            occurred_at=base_time,
        )
        candidate_repository = DjangoDetectionCandidateRepository()
        with self.unit_of_work:
            for candidate in [*candidates, rejected, other_merchant]:
                candidate_repository.save(candidate)

        result = ListPendingDetectionCandidatesUseCase(candidate_repository).execute(
            merchant_id=self.event.merchant_id,
            page=2,
            page_size=2,
        )

        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].candidate_id, candidates[2].id)

    def _make_order(self):
        from contexts.order_detection.domain.order import Order

        return Order.detect(
            merchant_id=self.event.merchant_id,
            contact_id=self.event.contact_id,
            detected_amount=self.event.detected_amount,
            confidence_score=self.event.confidence_score,
            source_message_id=self.event.source_message_id,
            occurred_at=self.event.occurred_at,
            source_candidate_id=self.event.candidate_id,
        )

    def _make_order_detected_event(self, order):
        from contexts.order_detection.application.events import OrderDetected

        return OrderDetected(
            order_id=order.id,
            merchant_id=order.merchant_id,
            contact_id=order.contact_id,
            source_message_id=self.event.source_message_id,
            detected_amount=order.detected_amount,
            confidence_score=order.confidence_score,
            source_candidate_id=self.event.candidate_id,
        )
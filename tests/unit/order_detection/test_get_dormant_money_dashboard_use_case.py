import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.order_detection.application.get_dormant_money_dashboard_use_case import (
    GetDormantMoneyDashboardUseCase,
)
from contexts.order_detection.domain.order import Order
from contexts.order_detection.domain.order_status import OrderStatus
from shared_kernel.application_exceptions import ValidationException
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class InMemoryOrderRepository:
    def __init__(self, orders):
        self.orders = orders
        self.request = None

    def find_dormant(self, merchant_id, older_than_hours):
        self.request = (merchant_id, older_than_hours)
        return self.orders


def make_order(merchant_id, amount, currency, created_at, status=None):
    order = Order.detect(
        merchant_id=merchant_id,
        contact_id=uuid4(),
        detected_amount=Money(amount, currency),
        confidence_score=ConfidenceScore(85),
        source_message_id=uuid4(),
        occurred_at=created_at,
    )
    if status is not None and status is not OrderStatus.PENDING_PAYMENT:
        order.change_status(status, occurred_at=created_at + timedelta(minutes=1))
    return order


class GetDormantMoneyDashboardUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        first_date = datetime(2026, 9, 20, tzinfo=timezone.utc)
        self.orders = [
            make_order(self.merchant_id, "100", "XOF", first_date),
            make_order(
                self.merchant_id,
                "25.50",
                "USD",
                first_date + timedelta(hours=2),
                OrderStatus.PAID_NOT_DELIVERED,
            ),
            make_order(self.merchant_id, "50", "XOF", first_date + timedelta(hours=4)),
            make_order(
                self.merchant_id,
                "900",
                "XOF",
                first_date + timedelta(hours=5),
                OrderStatus.CANCELLED,
            ),
        ]
        self.repository = InMemoryOrderRepository(self.orders)
        self.use_case = GetDormantMoneyDashboardUseCase(self.repository)

    def test_aggregates_separately_by_currency_and_keeps_open_order_summaries(self):
        result = self.use_case.execute(self.merchant_id, older_than_hours=48)

        totals = {money.currency: money.amount for money in result.totals_by_currency}
        self.assertEqual(totals, {"USD": Money("25.50", "USD").amount, "XOF": Money("150", "XOF").amount})
        self.assertEqual(len(result.orders), 3)
        self.assertNotIn(OrderStatus.CANCELLED.value, {summary.status for summary in result.orders})
        self.assertEqual(self.repository.request, (self.merchant_id, 48))

    def test_uses_default_age_threshold(self):
        self.use_case.execute(self.merchant_id)

        self.assertEqual(self.repository.request, (self.merchant_id, 24))

    def test_rejects_non_positive_or_non_integer_threshold(self):
        for invalid_value in (0, -1, 1.5, True):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(ValidationException):
                    self.use_case.execute(self.merchant_id, invalid_value)

        self.assertIsNone(self.repository.request)


if __name__ == "__main__":
    unittest.main()
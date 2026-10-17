import unittest
from uuid import uuid4

from contexts.crm.application.use_cases.create_segment_use_case import CreateSegmentUseCase
from contexts.crm.application.exceptions import (
    InvalidSegmentValueException,
    SegmentCurrencyRequiredException,
    UnknownSegmentFieldException,
    UnsupportedSegmentOperatorException,
)
from shared_kernel.value_objects.money import Money


class InMemorySegmentRepository:
    def __init__(self):
        self.segments = []

    def save(self, segment):
        self.segments.append(segment)


class CreateSegmentUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.repository = InMemorySegmentRepository()
        self.use_case = CreateSegmentUseCase(segment_repository=self.repository)

    def test_creates_segment_from_valid_definition(self):
        result = self.use_case.execute(
            merchant_id=uuid4(),
            name="VIP clients",
            definition_rule={
                "field": "total_spent",
                "operator": ">",
                "value": {"amount": "50000", "currency": "XOF"},
            },
        )

        self.assertEqual(len(self.repository.segments), 1)
        self.assertEqual(result["segment_id"], self.repository.segments[0].id)
        self.assertEqual(self.repository.segments[0].name, "VIP clients")
        self.assertEqual(self.repository.segments[0].definition_rule.field, "total_spent")
        self.assertEqual(self.repository.segments[0].definition_rule.operator, ">")
        self.assertEqual(
            self.repository.segments[0].definition_rule.value,
            Money("50000", "XOF"),
        )

    def test_rejects_unknown_field(self):
        with self.assertRaises(UnknownSegmentFieldException):
            self.use_case.execute(
                merchant_id=uuid4(),
                name="Unknown field",
                definition_rule={
                    "field": "unknown_metric",
                    "operator": ">",
                    "value": 10,
                },
            )

    def test_rejects_unsupported_operator(self):
        with self.assertRaises(UnsupportedSegmentOperatorException):
            self.use_case.execute(
                merchant_id=uuid4(),
                name="Unsupported operator",
                definition_rule={
                    "field": "order_count",
                    "operator": "in",
                    "value": 3,
                },
            )

    def test_rejects_total_spent_without_currency(self):
        with self.assertRaises(SegmentCurrencyRequiredException):
            self.use_case.execute(
                merchant_id=uuid4(),
                name="Invalid money rule",
                definition_rule={
                    "field": "total_spent",
                    "operator": ">",
                    "value": 50000,
                },
            )

    def test_contains_operator_is_supported_for_tags(self):
        self.use_case.execute(
            merchant_id=uuid4(),
            name="VIP tag",
            definition_rule={"field": "tags", "operator": "contains", "value": "vip"},
        )
        self.assertEqual(self.repository.segments[0].definition_rule.field, "tags")


if __name__ == "__main__":
    unittest.main()

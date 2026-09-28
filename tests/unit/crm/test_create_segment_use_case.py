import unittest
from uuid import uuid4

from contexts.crm.application.create_segment_use_case import CreateSegmentUseCase
from contexts.crm.application.exceptions import (
    UnknownSegmentFieldException,
    UnsupportedSegmentOperatorException,
)


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
                "value": 50000,
            },
        )

        self.assertEqual(len(self.repository.segments), 1)
        self.assertEqual(result["segment_id"], self.repository.segments[0].id)
        self.assertEqual(self.repository.segments[0].name, "VIP clients")
        self.assertEqual(self.repository.segments[0].definition_rule.field, "total_spent")
        self.assertEqual(self.repository.segments[0].definition_rule.operator, ">")
        self.assertEqual(self.repository.segments[0].definition_rule.value, 50000)

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


if __name__ == "__main__":
    unittest.main()

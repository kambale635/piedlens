from datetime import datetime, timezone
from uuid import uuid4

from django.test import TransactionTestCase

from contexts.crm.application.use_cases.create_segment_use_case import CreateSegmentUseCase
from contexts.crm.application.use_cases.get_segment_members_use_case import GetSegmentMembersUseCase
from contexts.crm.domain.entities.contact import Contact
from contexts.crm.infrastructure.persistence.django_contact_repository import DjangoContactRepository
from contexts.crm.infrastructure.persistence.django_segment_repository import DjangoSegmentRepository
from contexts.crm.infrastructure.persistence.django_unit_of_work import DjangoCRMUnitOfWork
from shared_kernel.value_objects.money import Money


class SegmentPersistenceIntegrationTests(TransactionTestCase):
    """Verify persisted rules drive merchant-scoped dynamic Contact membership."""

    def setUp(self):
        self.merchant_id = uuid4()
        self.contact_repository = DjangoContactRepository()
        self.segment_repository = DjangoSegmentRepository()
        self.unit_of_work = DjangoCRMUnitOfWork()
        self.xof_contact = Contact.create(
            merchant_id=self.merchant_id,
            platform_connection_id=uuid4(),
            external_identifier="xof-customer",
            display_name="XOF Customer",
            initial_total_spent=Money("0", "XOF"),
            occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
        )
        self.xof_contact.record_paid_order(
            uuid4(),
            Money("75000", "XOF"),
            datetime(2026, 9, 21, tzinfo=timezone.utc),
        )
        self.usd_contact = Contact.create(
            merchant_id=self.merchant_id,
            platform_connection_id=uuid4(),
            external_identifier="usd-customer",
            display_name="USD Customer",
            initial_total_spent=Money("1000", "USD"),
            occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
        )
        with self.unit_of_work:
            self.contact_repository.save(self.xof_contact)
            self.contact_repository.save(self.usd_contact)

    def test_persisted_money_rule_evaluates_members_only_in_its_currency(self):
        create_segment = CreateSegmentUseCase(
            self.segment_repository,
            type("Entitlements", (), {"entitlements_for": lambda *_: {"max_segments": 3}})(),
        )
        created = create_segment.execute(
            merchant_id=self.merchant_id,
            name="XOF high value",
            definition_rule={
                "field": "total_spent",
                "operator": ">",
                "value": {"amount": "50000", "currency": "XOF"},
            },
        )

        get_members = GetSegmentMembersUseCase(
            contact_repository=self.contact_repository,
            segment_repository=self.segment_repository,
            membership_cache=NoOpMembershipCache(),
        )
        result = get_members.execute(created["segment_id"], page=1, page_size=10)

        self.assertEqual(result["total_count"], 1)
        self.assertEqual(result["contacts"][0]["contact_id"], self.xof_contact.id)
        self.assertEqual(
            self.segment_repository.find_by_id(created["segment_id"]).definition_rule.value,
            Money("50000", "XOF"),
        )

    def test_contact_write_invalidates_membership_cache_after_commit(self):
        class CacheInvalidator:
            def __init__(inner_self):
                inner_self.invalidated = []

            def invalidate_merchant(inner_self, merchant_id):
                inner_self.invalidated.append(merchant_id)

        cache = CacheInvalidator()
        repository = DjangoContactRepository(segment_membership_cache=cache)
        with self.unit_of_work:
            repository.save(self.xof_contact)
            self.assertEqual(cache.invalidated, [])

        self.assertEqual(cache.invalidated, [self.merchant_id])


class NoOpMembershipCache:
    """Keep this ORM test independent of an external Redis service."""

    def get_members(self, segment_id, merchant_id, page, page_size):
        return None

    def set_members(self, segment_id, merchant_id, page, page_size, result):
        return None

    def invalidate_merchant(self, merchant_id):
        return None
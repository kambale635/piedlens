from datetime import datetime, timezone
from io import StringIO
import threading
from uuid import uuid4

from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, skipUnlessDBFeature

from contexts.billing.infrastructure.adapters.django_entitlement_reader import (
    DjangoEntitlementReader,
)
from contexts.billing.infrastructure.adapters.django_outbound_services import (
    DjangoOutboundUsageRecorder,
)
from contexts.billing.infrastructure.persistence.models import (
    BillingMerchantLockRecord,
    OutboundMessageReservationRecord,
    OutboundMessageUsageRecord,
    PlanDefinitionRecord,
    PlanEntitlementRecord,
)
from contexts.identity.infrastructure.persistence.models import MerchantRecord
from shared_kernel.application_exceptions import OutboundQuotaExceededException


@skipUnlessDBFeature("has_select_for_update")
class OutboundQuotaConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Quota row-lock concurrency requires PostgreSQL.")
        call_command("seed_billing_plans", stdout=StringIO())
        self.merchant_id = uuid4()
        MerchantRecord.objects.create(
            id=self.merchant_id,
            name="Concurrent quota merchant",
            country="US",
            preferred_language="en",
            currency="USD",
            subscription_plan="pro",
            created_at=datetime.now(timezone.utc),
        )
        plan = PlanDefinitionRecord.objects.get(code="pro")
        PlanEntitlementRecord.objects.update_or_create(
            plan=plan,
            key="outbound_monthly_cap",
            defaults={"value": 1},
        )
        BillingMerchantLockRecord.objects.create(merchant_id=self.merchant_id)

    def test_concurrent_reservations_never_exceed_merchant_cap(self):
        start = threading.Barrier(2)
        outcomes = []
        outcome_lock = threading.Lock()

        def reserve(idempotency_key):
            close_old_connections()
            try:
                start.wait(timeout=10)
                recorder = DjangoOutboundUsageRecorder(
                    DjangoEntitlementReader()
                )
                recorder.reserve(self.merchant_id, "utility", idempotency_key)
                outcome = "reserved"
            except OutboundQuotaExceededException:
                outcome = "rejected"
            except Exception as error:
                outcome = error
            finally:
                close_old_connections()
            with outcome_lock:
                outcomes.append(outcome)

        threads = [
            threading.Thread(target=reserve, args=(f"concurrent-{index}",))
            for index in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(outcomes), 2)
        unexpected = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
        self.assertEqual(unexpected, [])
        self.assertCountEqual(outcomes, ["reserved", "rejected"])
        self.assertEqual(
            OutboundMessageUsageRecord.objects.filter(merchant_id=self.merchant_id)
            .values_list("count", flat=True)
            .get(),
            1,
        )
        self.assertEqual(
            OutboundMessageReservationRecord.objects.filter(
                merchant_id=self.merchant_id
            ).count(),
            1,
        )
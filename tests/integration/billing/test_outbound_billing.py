from datetime import datetime, timezone
from io import StringIO
import json
from uuid import uuid4

from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase

from contexts.billing.application.use_cases.estimate_outbound_cost_use_case import (
    EstimateOutboundCostUseCase,
    OutboundRateNotConfiguredException,
)
from contexts.billing.application.use_cases.upsert_outbound_rate_use_case import (
    UpsertOutboundRateUseCase,
)
from contexts.billing.application.use_cases.upsert_outbound_rate_use_case import (
    UpsertOutboundRateUseCase,
)
from contexts.billing.application.use_cases.upsert_outbound_rate_use_case import (
    UpsertOutboundRateUseCase,
)
from contexts.billing.infrastructure.persistence.django_plan_admin_repository import (
    DjangoPlanAdminRepository,
)
from contexts.identity.infrastructure.adapters.django_merchant_country_reader import (
    DjangoMerchantCountryReader,
)
from contexts.billing.infrastructure.adapters.django_outbound_services import (
    DjangoOutboundCostEstimator,
    DjangoOutboundUsageRecorder,
)
from contexts.billing.infrastructure.adapters.django_entitlement_reader import (
    DjangoEntitlementReader,
)
from contexts.identity.infrastructure.adapters.django_merchant_plan_reader import (
    DjangoMerchantPlanReader,
)
from contexts.billing.infrastructure.persistence.models import (
    OutboundMessageReservationRecord,
    OutboundMessageUsageRecord,
    OutboundRateRecord,
    PlanDefinitionRecord,
    PlanEntitlementRecord,
)
from contexts.billing.infrastructure.persistence.django_plan_admin_repository import (
    DjangoPlanAdminRepository,
)
from contexts.billing.infrastructure.persistence.django_plan_admin_repository import (
    DjangoPlanAdminRepository,
)
from contexts.identity.infrastructure.persistence.models import MerchantRecord
from contexts.identity.infrastructure.adapters.django_merchant_currency_reader import (
    DjangoMerchantCurrencyReader,
)
from shared_kernel.application_exceptions import OutboundQuotaExceededException


class OutboundBillingTests(TestCase):
    def setUp(self):
        call_command("seed_billing_plans", stdout=StringIO())
        self.merchant_id = uuid4()
        MerchantRecord.objects.create(
            id=self.merchant_id,
            name="Outbound merchant",
            country="US",
            preferred_language="en",
            currency="USD",
            subscription_plan="pro",
            created_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
        )
        pro = PlanDefinitionRecord.objects.get(code="pro")
        PlanEntitlementRecord.objects.update_or_create(
            plan=pro, key="outbound_monthly_cap", defaults={"value": 2}
        )

    def test_estimate_uses_configured_country_rate_and_no_currency_conversion(self):
        OutboundRateRecord.objects.create(
            country="US",
            category="marketing",
            currency="USD",
            amount_minor=4,
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            valid_until=None,
            is_active=True,
        )
        use_case = EstimateOutboundCostUseCase(
            DjangoMerchantCountryReader(),
            DjangoMerchantCurrencyReader(),
            DjangoOutboundCostEstimator(),
        )

        result = use_case.execute(self.merchant_id, "marketing", 3)

        self.assertEqual(result.estimate["amountMinor"], 12)
        self.assertEqual(result.estimate["currency"], "USD")
        self.assertEqual(result.estimate["chargeProcessor"], "meta_direct")

    def test_admin_rate_change_is_visible_without_redeployment(self):
        admin = UpsertOutboundRateUseCase(DjangoPlanAdminRepository())
        valid_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
        admin.execute("US", "utility", "USD", 3, valid_from, None)
        estimator = EstimateOutboundCostUseCase(
            DjangoMerchantCountryReader(),
            DjangoMerchantCurrencyReader(),
            DjangoOutboundCostEstimator(),
        )

        initial = estimator.execute(self.merchant_id, "utility", 2)
        admin.execute("US", "utility", "USD", 7, valid_from, None)
        changed = estimator.execute(self.merchant_id, "utility", 2)

        self.assertEqual(initial.estimate["amountMinor"], 6)
        self.assertEqual(changed.estimate["amountMinor"], 14)

    def test_admin_rate_update_changes_estimate_without_redeployment(self):
        rate_admin = UpsertOutboundRateUseCase(DjangoPlanAdminRepository())
        valid_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rate_admin.execute("US", "utility", "USD", 3, valid_from, None)
        estimator = EstimateOutboundCostUseCase(
            DjangoMerchantCountryReader(),
            DjangoMerchantCurrencyReader(),
            DjangoOutboundCostEstimator(),
        )

        first = estimator.execute(self.merchant_id, "utility", 2)
        rate_admin.execute("US", "utility", "USD", 7, valid_from, None)
        second = estimator.execute(self.merchant_id, "utility", 2)

        self.assertEqual(first.estimate["amountMinor"], 6)
        self.assertEqual(second.estimate["amountMinor"], 14)

    def test_admin_rate_change_is_visible_to_estimator_without_redeployment(self):
        rate_admin = UpsertOutboundRateUseCase(DjangoPlanAdminRepository())
        valid_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rate_admin.execute("US", "utility", "USD", 3, valid_from, None)
        estimator = EstimateOutboundCostUseCase(
            DjangoMerchantCountryReader(),
            DjangoMerchantCurrencyReader(),
            DjangoOutboundCostEstimator(),
        )

        first = estimator.execute(self.merchant_id, "utility", 2)
        rate_admin.execute("US", "utility", "USD", 7, valid_from, None)
        second = estimator.execute(self.merchant_id, "utility", 2)

        self.assertEqual(first.estimate["amountMinor"], 6)
        self.assertEqual(second.estimate["amountMinor"], 14)

    def test_missing_rate_is_explicit_and_api_cap_is_global_and_idempotent(self):
        with self.assertRaises(OutboundRateNotConfiguredException):
            EstimateOutboundCostUseCase(
                DjangoMerchantCountryReader(),
                DjangoMerchantCurrencyReader(),
                DjangoOutboundCostEstimator(),
            ).execute(self.merchant_id, "service")

        recorder = DjangoOutboundUsageRecorder(
            DjangoEntitlementReader(DjangoMerchantPlanReader())
        )
        recorder.reserve(self.merchant_id, "marketing", "campaign-a:contact-a")
        recorder.reserve(self.merchant_id, "marketing", "campaign-a:contact-a")
        recorder.reserve(self.merchant_id, "utility", "campaign-a:contact-b")
        with self.assertRaises(OutboundQuotaExceededException):
            recorder.reserve(self.merchant_id, "service", "campaign-a:contact-c")

        self.assertEqual(
            OutboundMessageUsageRecord.objects.filter(merchant_id=self.merchant_id)
            .aggregate(total=Sum("count"))["total"],
            2,
        )
        self.assertEqual(
            OutboundMessageReservationRecord.objects.filter(
                merchant_id=self.merchant_id
            ).count(),
            2,
        )

    def test_outbound_estimate_and_usage_routes_are_tenant_scoped(self):
        from contexts.access_control.infrastructure.persistence.models import (
            RoleAssignmentRecord,
            RoleRecord,
        )
        from contexts.identity.infrastructure.adapters.django_security_services import (
            DjangoTokenService,
        )
        from contexts.identity.infrastructure.persistence.models import UserRecord

        OutboundRateRecord.objects.create(
            country="US",
            category="utility",
            currency="USD",
            amount_minor=2,
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            valid_until=None,
            is_active=True,
        )
        user = UserRecord.objects.create(
            phone_number="+14155550199",
            email=None,
            password_hash="test-only",
            status="active",
            created_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
        )
        permissions = ["outbound.estimate", "outbound.usage.read"]
        role = RoleRecord.objects.create(
            name="Outbound test",
            permissions=permissions,
            is_system=False,
            created_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
            created_by=str(user.id),
        )
        RoleAssignmentRecord.objects.create(
            user_id=user.id,
            role_id=role.id,
            scope_type="merchant",
            scope_id=self.merchant_id,
            granted_by=str(user.id),
            granted_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
        )
        access_token = DjangoTokenService().issue_tokens(user.id)["accessToken"]
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {access_token}",
            "HTTP_X_MERCHANT_ID": str(self.merchant_id),
        }

        estimate = self.client.post(
            "/api/v1/outbound/estimate",
            data=json.dumps({"category": "utility", "count": 2}),
            content_type="application/json",
            **headers,
        )
        usage = self.client.get("/api/v1/outbound/usage", **headers)

        self.assertEqual(estimate.status_code, 200)
        self.assertEqual(estimate.json()["estimate"]["amountMinor"], 4)
        self.assertEqual(estimate.json()["estimate"]["chargeProcessor"], "meta_direct")
        self.assertEqual(usage.status_code, 200)
        self.assertEqual(usage.json()["usage"], [])
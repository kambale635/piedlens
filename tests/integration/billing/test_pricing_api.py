from django.test import TestCase

from contexts.billing.infrastructure.persistence.models import (
    PlanDefinitionRecord,
    PlanPriceRecord,
)


class PricingApiTests(TestCase):
    def test_public_catalog_prefers_exact_country_then_uses_fallback(self):
        starter = PlanDefinitionRecord.objects.create(code="starter", display_order=1)
        PlanPriceRecord.objects.create(
            plan=starter,
            country="*",
            currency="USD",
            period_days=30,
            amount_minor=200,
        )
        PlanPriceRecord.objects.create(
            plan=starter,
            country="US",
            currency="USD",
            period_days=30,
            amount_minor=250,
        )
        PlanPriceRecord.objects.create(
            plan=starter,
            country="*",
            currency="USD",
            period_days=365,
            amount_minor=2000,
        )

        response = self.client.get("/api/v1/pricing?country=us")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["country"], "US")
        self.assertEqual(
            payload["plans"][0]["prices"],
            [
                {
                    "country": "US",
                    "currency": "USD",
                    "periodDays": 30,
                    "amountMinor": 250,
                },
                {
                    "country": "*",
                    "currency": "USD",
                    "periodDays": 365,
                    "amountMinor": 2000,
                },
            ],
        )

    def test_public_catalog_rejects_missing_country(self):
        response = self.client.get("/api/v1/pricing")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errorCode"], "VALIDATION_ERROR")
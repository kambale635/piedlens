import json

from django.test import TestCase

from contexts.identity.infrastructure.persistence.models import (
    MerchantRecord,
    OutboxEventRecord,
    UserRecord,
)


class IdentityApiTests(TestCase):
    def test_create_merchant_requires_authentication(self):
        response = self.client.post(
            "/api/v1/merchants",
            data=json.dumps({
                "name": "Acme",
                "country": "FR",
                "preferredLanguage": "fr",
                "currency": "EUR",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_register_authenticate_and_create_merchant(self):
        password = "correct-horse-battery-7"
        response = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps({"phoneNumber": "+14155550123", "password": password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        user = UserRecord.objects.get(phone_number="+14155550123")
        self.assertNotEqual(user.password_hash, password)
        self.assertNotIn(password, user.password_hash)

        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"phoneNumber": "+14155550123", "password": password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        access_token = response.json()["accessToken"]

        response = self.client.post(
            "/api/v1/merchants",
            data=json.dumps({
                "name": "Acme",
                "country": "FR",
                "preferredLanguage": "fr",
                "currency": "EUR",
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        self.assertEqual(response.status_code, 201, response.content)
        merchant = MerchantRecord.objects.get(id=response.json()["merchantId"])
        self.assertFalse(hasattr(merchant, "owner_user_id"))
        self.assertFalse(hasattr(user, "merchant_id"))
        self.assertTrue(
            OutboxEventRecord.objects.filter(
                event_type="MerchantRegistered",
                payload__owner_user_id=str(user.id),
            ).exists()
        )
import json

from django.test import TestCase

from contexts.identity.infrastructure.persistence.models import AuthSessionRecord


class IdentitySessionLifecycleTests(TestCase):
    def test_refresh_rotation_and_reuse_revoke_the_entire_family(self):
        tokens = self._register_and_login()

        rotated = self.client.post(
            "/api/v1/auth/refresh",
            data=json.dumps({"refreshToken": tokens["refreshToken"]}),
            content_type="application/json",
        )

        self.assertEqual(rotated.status_code, 200)
        replacement = rotated.json()
        self.assertNotEqual(replacement["refreshToken"], tokens["refreshToken"])
        self.assertNotEqual(replacement["accessToken"], tokens["accessToken"])
        self.assertEqual(AuthSessionRecord.objects.filter(revoked_at__isnull=True).count(), 1)

        replay = self.client.post(
            "/api/v1/auth/refresh",
            data=json.dumps({"refreshToken": tokens["refreshToken"]}),
            content_type="application/json",
        )
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(AuthSessionRecord.objects.filter(revoked_at__isnull=True).count(), 0)

        family_replay = self.client.post(
            "/api/v1/auth/refresh",
            data=json.dumps({"refreshToken": replacement["refreshToken"]}),
            content_type="application/json",
        )
        self.assertEqual(family_replay.status_code, 401)

    def test_logout_revokes_refresh_and_associated_access_token(self):
        tokens = self._register_and_login()

        logout = self.client.post(
            "/api/v1/auth/logout",
            data=json.dumps({"refreshToken": tokens["refreshToken"]}),
            content_type="application/json",
        )
        refresh = self.client.post(
            "/api/v1/auth/refresh",
            data=json.dumps({"refreshToken": tokens["refreshToken"]}),
            content_type="application/json",
        )
        protected = self.client.post(
            "/api/v1/merchants",
            data=json.dumps({
                "name": "Shop",
                "country": "FR",
                "preferredLanguage": "fr",
                "currency": "EUR",
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['accessToken']}",
        )

        self.assertEqual(logout.status_code, 200)
        self.assertEqual(logout.json(), {"loggedOut": True})
        self.assertEqual(refresh.status_code, 401)
        self.assertEqual(protected.status_code, 401)

    def test_logout_all_revokes_every_user_session_and_access_token(self):
        tokens = self._register_and_login()

        logout_all = self.client.post(
            "/api/v1/auth/logout-all",
            data="{}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['accessToken']}",
        )
        refresh = self.client.post(
            "/api/v1/auth/refresh",
            data=json.dumps({"refreshToken": tokens["refreshToken"]}),
            content_type="application/json",
        )
        protected = self.client.post(
            "/api/v1/merchants",
            data=json.dumps({
                "name": "Shop",
                "country": "FR",
                "preferredLanguage": "fr",
                "currency": "EUR",
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['accessToken']}",
        )

        self.assertEqual(logout_all.status_code, 200)
        self.assertEqual(logout_all.json()["revokedSessionCount"], 1)
        self.assertEqual(refresh.status_code, 401)
        self.assertEqual(protected.status_code, 401)

    def _register_and_login(self):
        self.client.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "phoneNumber": "+14155550123",
                "password": "correct-horse-battery-7",
            }),
            content_type="application/json",
        )
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({
                "phoneNumber": "+14155550123",
                "password": "correct-horse-battery-7",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()
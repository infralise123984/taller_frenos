"""Pruebas de cifrado, TOTP y flujos de autenticación en dos pasos."""

from __future__ import annotations

import time

from django.conf import settings
from django.contrib.admin import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.accounts.admin import UserAdmin
from apps.accounts.exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
    TwoFactorInvalidCodeError,
)
from apps.accounts.models import User
from apps.accounts.services.throttling import RateLimiter
from apps.accounts.services.two_factor import (
    TwoFactorService,
    _code_for_counter,
    decrypt_totp_secret,
    encrypt_totp_secret,
    matching_totp_counter,
)

EMAIL = "recepcion@taller.cl"
PASSWORD = "clave-de-prueba-1234"
CLIENT_IP = "192.168.1.50"


class TwoFactorCryptographyTests(TestCase):
    def test_totp_matches_rfc_6238_sha1_vector(self) -> None:
        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"

        self.assertEqual(
            matching_totp_counter(secret=secret, code="287082", timestamp=59),
            1,
        )

    def test_encryption_round_trip_does_not_store_the_secret_in_clear(self) -> None:
        secret = "JBSWY3DPEHPK3PXP"
        ciphertext = encrypt_totp_secret(secret)

        self.assertNotEqual(ciphertext, secret)
        self.assertEqual(decrypt_totp_secret(ciphertext), secret)


@override_settings(LOGIN_MAX_FAILED_ATTEMPTS=2, LOGIN_LOCKOUT_SECONDS=900)
class TwoFactorServiceTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.user = User.objects.create_user(email=EMAIL, password=PASSWORD)
        self.limiter = RateLimiter(
            namespace="test-two-factor",
            max_events=2,
            window_seconds=900,
        )
        self.service = TwoFactorService(limiter=self.limiter)
        self.secret = "JBSWY3DPEHPK3PXP"
        self.user.totp_enabled = True
        self.user.totp_secret_encrypted = encrypt_totp_secret(self.secret)
        self.user.save(update_fields=["totp_enabled", "totp_secret_encrypted"])

    def test_rejects_reuse_of_the_same_totp_code(self) -> None:
        counter = int(time.time() // 30)
        code = _code_for_counter(self.secret, counter)
        self.service.verify_login_code(user=self.user, code=code, client_ip=CLIENT_IP)

        with self.assertRaises(TwoFactorInvalidCodeError):
            self.service.verify_login_code(user=self.user, code=code, client_ip=CLIENT_IP)

    def test_locks_totp_verification_after_the_configured_failures(self) -> None:
        for _ in range(2):
            with self.assertRaises(TwoFactorInvalidCodeError):
                self.service.verify_login_code(
                    user=self.user,
                    code="000000",
                    client_ip=CLIENT_IP,
                )

        with self.assertRaises(AccountLockedError):
            self.service.verify_login_code(
                user=self.user,
                code="000000",
                client_ip=CLIENT_IP,
            )

    def test_enabling_and_disabling_require_current_password_and_totp(self) -> None:
        self.user.totp_enabled = False
        self.user.totp_secret_encrypted = ""
        self.user.totp_last_verified_step = None
        self.user.save(
            update_fields=["totp_enabled", "totp_secret_encrypted", "totp_last_verified_step"]
        )
        self.service.begin_setup(user=self.user, password=PASSWORD, client_ip=CLIENT_IP)
        pending_secret = self.service.pending_secret(user=self.user)
        self.assertIsNotNone(pending_secret)
        counter = int(time.time() // 30)
        setup_code = _code_for_counter(pending_secret, counter - 1)

        with self.assertRaises(InvalidCredentialsError):
            self.service.enable(
                user=self.user,
                password="incorrecta",
                code=setup_code,
                client_ip=CLIENT_IP,
            )

        self.service.enable(
            user=self.user,
            password=PASSWORD,
            code=setup_code,
            client_ip=CLIENT_IP,
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.totp_enabled)
        self.assertNotEqual(self.user.totp_secret_encrypted, pending_secret)
        self.assertEqual(decrypt_totp_secret(self.user.totp_secret_encrypted), pending_secret)

        disable_code = _code_for_counter(pending_secret, counter)
        self.service.disable(
            user=self.user,
            password=PASSWORD,
            code=disable_code,
            client_ip=CLIENT_IP,
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.totp_enabled)
        self.assertEqual(self.user.totp_secret_encrypted, "")


class TwoFactorViewTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.user = User.objects.create_user(email=EMAIL, password=PASSWORD)
        self.login_url = reverse("accounts:login")
        self.two_factor_url = reverse("accounts:two_factor")

    def test_setup_generates_private_qr_and_can_be_confirmed(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            self.two_factor_url,
            {"action": "begin", "password": PASSWORD},
        )

        self.assertRedirects(response, self.two_factor_url)
        setup_page = self.client.get(self.two_factor_url)
        secret = setup_page.context["pending_secret"]
        self.assertIsNotNone(secret)
        self.assertIn("no-store", setup_page["Cache-Control"])

        qr_response = self.client.get(reverse("accounts:two_factor_qr"))
        self.assertEqual(qr_response.status_code, 200)
        self.assertEqual(qr_response["Content-Type"], "image/png")
        self.assertIn("no-store", qr_response["Cache-Control"])
        self.assertTrue(qr_response.content.startswith(b"\x89PNG"))

        counter = int(time.time() // 30)
        code = _code_for_counter(secret, counter - 1)
        response = self.client.post(
            self.two_factor_url,
            {
                "action": "enable",
                "password": PASSWORD,
                "code": code,
            },
        )
        self.assertRedirects(response, self.two_factor_url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.totp_enabled)

    def test_login_requires_totp_before_creating_an_authenticated_session(self) -> None:
        secret = "JBSWY3DPEHPK3PXP"
        self.user.totp_enabled = True
        self.user.totp_secret_encrypted = encrypt_totp_secret(secret)
        self.user.save(update_fields=["totp_enabled", "totp_secret_encrypted"])

        response = self.client.post(
            self.login_url,
            {"email": EMAIL, "password": PASSWORD, "next": "/taller/"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verificación en dos pasos")
        self.assertNotIn("_auth_user_id", self.client.session)

        code = _code_for_counter(secret, int(time.time() // 30))
        response = self.client.post(
            self.login_url,
            {"action": "verify_totp", "code": code, "next": "/taller/"},
        )
        self.assertRedirects(response, "/taller/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    @override_settings(SESSION_COOKIE_AGE=3600)
    def test_sesion_autenticada_recupera_duracion_normal_tras_desafio_totp(self) -> None:
        secret = "JBSWY3DPEHPK3PXP"
        self.user.totp_enabled = True
        self.user.totp_secret_encrypted = encrypt_totp_secret(secret)
        self.user.save(update_fields=["totp_enabled", "totp_secret_encrypted"])

        self.client.post(self.login_url, {"email": EMAIL, "password": PASSWORD})
        self.assertEqual(self.client.session.get_expiry_age(), 300)

        response = self.client.post(
            self.login_url,
            {
                "action": "verify_totp",
                "code": _code_for_counter(secret, int(time.time() // 30)),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get_expiry_age(), 3600)
        self.assertEqual(response.cookies[settings.SESSION_COOKIE_NAME]["max-age"], 3600)

    def test_totp_challenge_expires_after_five_minutes(self) -> None:
        session = self.client.session
        session["two_factor_pending_user_id"] = self.user.pk
        session["two_factor_pending_started_at"] = time.time() - 301
        session.save()

        response = self.client.post(
            self.login_url,
            {"action": "verify_totp", "code": "123456"},
        )

        self.assertRedirects(response, self.login_url)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotIn("two_factor_pending_user_id", self.client.session)


class TwoFactorAdminRecoveryTests(TestCase):
    def test_admin_action_clears_encrypted_secrets_and_disables_two_factor(self) -> None:
        user = User.objects.create_user(email=EMAIL, password=PASSWORD)
        user.totp_enabled = True
        user.totp_secret_encrypted = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
        user.totp_pending_secret_encrypted = encrypt_totp_secret("MZXW6YTBOI======")
        user.totp_last_verified_step = 123
        user.save(
            update_fields=[
                "totp_enabled",
                "totp_secret_encrypted",
                "totp_pending_secret_encrypted",
                "totp_last_verified_step",
            ]
        )
        administrator = User.objects.create_user(
            email="admin@taller.cl",
            password=PASSWORD,
            is_staff=True,
        )
        request = RequestFactory().post("/admin/accounts/user/")
        request.user = administrator
        request.session = {}
        request._messages = FallbackStorage(request)

        UserAdmin(User, AdminSite()).reset_two_factor(
            request,
            User.objects.filter(pk=user.pk),
        )

        user.refresh_from_db()
        self.assertFalse(user.totp_enabled)
        self.assertEqual(user.totp_secret_encrypted, "")
        self.assertEqual(user.totp_pending_secret_encrypted, "")
        self.assertIsNone(user.totp_pending_expires_at)
        self.assertIsNone(user.totp_last_verified_step)

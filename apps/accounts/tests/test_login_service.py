"""Pruebas del servicio de autenticación."""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.accounts.exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
)
from apps.accounts.models import User
from apps.accounts.services.authentication import LoginService
from apps.accounts.services.throttling import RateLimiter

AJUSTES = {
    "LOGIN_MAX_FAILED_ATTEMPTS": 3,
    "LOGIN_LOCKOUT_SECONDS": 900,
}

EMAIL = "recepcion@taller.cl"
CLAVE = "clave-de-prueba-1234"
IP = "192.168.1.50"


@override_settings(**AJUSTES)
class LoginServiceTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.service = self._construir_servicio()
        self.user = User.objects.create_user(
            email=EMAIL,
            password=CLAVE,
            full_name="Encargada Taller",
        )

    def _construir_servicio(self) -> LoginService:
        return LoginService(
            password_limiter=RateLimiter(
                namespace="test-password",
                max_events=AJUSTES["LOGIN_MAX_FAILED_ATTEMPTS"],
                window_seconds=AJUSTES["LOGIN_LOCKOUT_SECONDS"],
            ),
        )

    # -- Contraseña --------------------------------------------------------

    def test_acepta_credenciales_correctas(self) -> None:
        user = self.service.authenticate_with_password(email=EMAIL, password=CLAVE, client_ip=IP)

        user.refresh_from_db()
        self.assertEqual(user.pk, self.user.pk)
        self.assertIsNotNone(user.last_password_login)

    def test_normaliza_el_correo_ignorando_mayusculas(self) -> None:
        user = self.service.authenticate_with_password(
            email="  RECEPCION@Taller.CL ", password=CLAVE, client_ip=IP
        )

        self.assertEqual(user.pk, self.user.pk)

    def test_rechaza_una_contrasena_incorrecta(self) -> None:
        with self.assertRaises(InvalidCredentialsError):
            self.service.authenticate_with_password(
                email=EMAIL, password="incorrecta", client_ip=IP
            )

    def test_un_correo_desconocido_produce_el_mismo_error_que_una_clave_mala(self) -> None:
        with self.assertRaises(InvalidCredentialsError) as desconocido:
            self.service.authenticate_with_password(
                email="nadie@taller.cl", password=CLAVE, client_ip=IP
            )

        with self.assertRaises(InvalidCredentialsError) as clave_mala:
            self.service.authenticate_with_password(
                email=EMAIL, password="incorrecta", client_ip=IP
            )

        self.assertEqual(str(desconocido.exception), str(clave_mala.exception))

    def test_una_cuenta_deshabilitada_se_rechaza_sin_revelar_el_motivo(self) -> None:
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        with self.assertRaises(InvalidCredentialsError):
            self.service.authenticate_with_password(email=EMAIL, password=CLAVE, client_ip=IP)

    def test_bloquea_tras_superar_los_intentos_permitidos(self) -> None:
        for _ in range(AJUSTES["LOGIN_MAX_FAILED_ATTEMPTS"]):
            with self.assertRaises(InvalidCredentialsError):
                self.service.authenticate_with_password(
                    email=EMAIL, password="incorrecta", client_ip=IP
                )

        with self.assertRaises(AccountLockedError) as contexto:
            self.service.authenticate_with_password(email=EMAIL, password=CLAVE, client_ip=IP)

        self.assertGreater(contexto.exception.retry_after_seconds, 0)

    def test_un_acceso_exitoso_limpia_los_intentos_fallidos(self) -> None:
        for _ in range(AJUSTES["LOGIN_MAX_FAILED_ATTEMPTS"] - 1):
            with self.assertRaises(InvalidCredentialsError):
                self.service.authenticate_with_password(
                    email=EMAIL, password="incorrecta", client_ip=IP
                )

        self.service.authenticate_with_password(email=EMAIL, password=CLAVE, client_ip=IP)

        # La ventana volvió a cero: los fallos previos ya no cuentan.
        for _ in range(AJUSTES["LOGIN_MAX_FAILED_ATTEMPTS"] - 1):
            with self.assertRaises(InvalidCredentialsError):
                self.service.authenticate_with_password(
                    email=EMAIL, password="incorrecta", client_ip=IP
                )

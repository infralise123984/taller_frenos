"""Pruebas del servicio de autenticación."""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.accounts.exceptions import (
    AccountInactiveError,
    AccountLockedError,
    InvalidCredentialsError,
    OtpInvalidError,
    OtpThrottledError,
)
from apps.accounts.models import User
from apps.accounts.providers.base import OtpProvider
from apps.accounts.services.authentication import LoginService
from apps.accounts.services.throttling import Cooldown, RateLimiter

AJUSTES = {
    "LOGIN_MAX_FAILED_ATTEMPTS": 3,
    "LOGIN_LOCKOUT_SECONDS": 900,
    "OTP_MAX_REQUESTS_PER_HOUR": 5,
    "OTP_RESEND_COOLDOWN_SECONDS": 60,
}

EMAIL = "recepcion@taller.cl"
CLAVE = "clave-de-prueba-1234"
IP = "192.168.1.50"


class ProveedorOtpFalso(OtpProvider):
    """Doble de prueba: registra envíos y valida contra un mapa en memoria."""

    def __init__(self) -> None:
        self.enviados: list[tuple[str, str | None]] = []
        self.codigos: dict[str, str] = {}

    def send_code(self, *, email: str, request_ip: str | None = None) -> None:
        self.enviados.append((email, request_ip))

    def verify_code(self, *, email: str, code: str) -> bool:
        return self.codigos.get(email) == code


@override_settings(**AJUSTES)
class LoginServiceTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.provider = ProveedorOtpFalso()
        self.service = self._construir_servicio()
        self.user = User.objects.create_user(
            email=EMAIL,
            password=CLAVE,
            full_name="Encargada Taller",
        )

    def _construir_servicio(self) -> LoginService:
        return LoginService(
            otp_provider=self.provider,
            password_limiter=RateLimiter(
                namespace="test-password",
                max_events=AJUSTES["LOGIN_MAX_FAILED_ATTEMPTS"],
                window_seconds=AJUSTES["LOGIN_LOCKOUT_SECONDS"],
            ),
            otp_limiter=RateLimiter(
                namespace="test-otp",
                max_events=AJUSTES["OTP_MAX_REQUESTS_PER_HOUR"],
                window_seconds=3600,
            ),
            otp_cooldown=Cooldown(
                namespace="test-cooldown",
                seconds=AJUSTES["OTP_RESEND_COOLDOWN_SECONDS"],
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

    # -- Solicitud de código ------------------------------------------------

    def test_envia_el_codigo_a_una_cuenta_registrada(self) -> None:
        self.service.request_otp(email=EMAIL, client_ip=IP)

        self.assertEqual(self.provider.enviados, [(EMAIL, IP)])

    def test_no_envia_codigo_para_correos_sin_cuenta(self) -> None:
        self.service.request_otp(email="nadie@taller.cl", client_ip=IP)

        self.assertEqual(self.provider.enviados, [])

    def test_no_envia_codigo_a_una_cuenta_deshabilitada(self) -> None:
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.service.request_otp(email=EMAIL, client_ip=IP)

        self.assertEqual(self.provider.enviados, [])

    def test_aplica_una_espera_minima_entre_solicitudes(self) -> None:
        self.service.request_otp(email=EMAIL, client_ip=IP)

        with self.assertRaises(OtpThrottledError):
            self.service.request_otp(email=EMAIL, client_ip=IP)

    def test_limita_la_cantidad_de_solicitudes_por_hora(self) -> None:
        for _ in range(AJUSTES["OTP_MAX_REQUESTS_PER_HOUR"]):
            self.service._otp_cooldown.clear(f"email:{EMAIL}")  # noqa: SLF001 - simula el paso del tiempo
            self.service.request_otp(email=EMAIL, client_ip=IP)

        self.service._otp_cooldown.clear(f"email:{EMAIL}")  # noqa: SLF001

        with self.assertRaises(OtpThrottledError):
            self.service.request_otp(email=EMAIL, client_ip=IP)

    # -- Acceso con código --------------------------------------------------

    def test_acepta_un_codigo_valido(self) -> None:
        self.provider.codigos[EMAIL] = "123456"

        user = self.service.authenticate_with_otp(email=EMAIL, code="123456", client_ip=IP)

        user.refresh_from_db()
        self.assertEqual(user.pk, self.user.pk)
        self.assertIsNotNone(user.last_otp_login)

    def test_rechaza_un_codigo_incorrecto(self) -> None:
        self.provider.codigos[EMAIL] = "123456"

        with self.assertRaises(OtpInvalidError):
            self.service.authenticate_with_otp(email=EMAIL, code="999999", client_ip=IP)

    def test_rechaza_un_codigo_valido_sin_cuenta_local(self) -> None:
        self.provider.codigos["nadie@taller.cl"] = "123456"

        with self.assertRaises(OtpInvalidError):
            self.service.authenticate_with_otp(email="nadie@taller.cl", code="123456", client_ip=IP)

    def test_rechaza_un_codigo_valido_de_una_cuenta_deshabilitada(self) -> None:
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.provider.codigos[EMAIL] = "123456"

        with self.assertRaises(AccountInactiveError):
            self.service.authenticate_with_otp(email=EMAIL, code="123456", client_ip=IP)

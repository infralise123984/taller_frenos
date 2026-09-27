"""
Servicio de autenticación.

Orquesta los dos mecanismos de acceso definidos para el taller:

  1. Correo + contraseña (Django ``authenticate``).
  2. Correo + código temporal (delegado a un ``OtpProvider``).

Reglas de diseño:
  * No conoce HTTP: recibe datos primitivos y devuelve el usuario autenticado.
    La creación de la sesión la realiza la vista (separación dominio/transporte).
  * No revela la existencia de cuentas: los fallos se traducen a excepciones
    de dominio con mensajes genéricos.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone

from apps.accounts.exceptions import (
    AccountInactiveError,
    AccountLockedError,
    InvalidCredentialsError,
    OtpInvalidError,
    OtpThrottledError,
)
from apps.accounts.models import User
from apps.accounts.providers import get_otp_provider
from apps.accounts.providers.base import OtpProvider
from apps.accounts.services.throttling import Cooldown, RateLimiter

logger = logging.getLogger(__name__)

AuthenticateFn = Callable[..., User | None]
OTP_REQUESTS_WINDOW_SECONDS = 3600


class LoginService:
    """Casos de uso de acceso al sistema."""

    def __init__(
        self,
        *,
        otp_provider: OtpProvider,
        password_limiter: RateLimiter,
        otp_limiter: RateLimiter,
        otp_cooldown: Cooldown,
        users=User.objects,
        authenticate_fn: AuthenticateFn = authenticate,
    ) -> None:
        self._otp_provider = otp_provider
        self._password_limiter = password_limiter
        self._otp_limiter = otp_limiter
        self._otp_cooldown = otp_cooldown
        self._users = users
        self._authenticate = authenticate_fn

    # -- Acceso con contraseña --------------------------------------------

    def authenticate_with_password(
        self,
        *,
        email: str,
        password: str,
        client_ip: str | None = None,
    ) -> User:
        """Valida correo y contraseña, o levanta un error de dominio."""
        normalized = email.strip().lower()
        keys = self._attempt_keys(normalized, client_ip)

        self._assert_not_locked(keys)

        user = self._authenticate(username=normalized, password=password)
        if user is None:
            self._register_failures(keys)
            # Mismo mensaje si la cuenta no existe, si la contraseña es errónea
            # o si está deshabilitada: evita la enumeración de usuarios.
            raise InvalidCredentialsError("Credenciales inválidas.")

        self._clear_failures(keys)
        self._record_login(user, via_otp=False)
        return user

    # -- Acceso con código temporal ---------------------------------------

    def request_otp(self, *, email: str, client_ip: str | None = None) -> None:
        """Solicita el envío de un código al correo indicado."""
        normalized = email.strip().lower()
        email_key = f"email:{normalized}"
        ip_key = f"ip:{client_ip}" if client_ip else None

        keys = [email_key] + ([ip_key] if ip_key else [])
        for key in keys:
            if self._otp_limiter.is_exceeded(key):
                raise OtpThrottledError(self._otp_limiter.retry_after_seconds(key))

        if self._otp_cooldown.is_active(email_key):
            raise OtpThrottledError(self._otp_cooldown.remaining_seconds(email_key))

        # Se registra antes de enviar: un fallo de entrega no debe habilitar
        # reintentos ilimitados.
        for key in keys:
            self._otp_limiter.register(key)
        self._otp_cooldown.start(email_key)

        user = self._users.by_email(normalized).first()
        if user is None or not user.is_active:
            # Se responde igual que en el caso exitoso para no filtrar qué
            # correos existen. El detalle queda solo en los logs del servidor.
            logger.warning("Solicitud de código para cuenta inexistente o inactiva.")
            return

        self._otp_provider.send_code(email=normalized, request_ip=client_ip)
        logger.info("Código de acceso emitido para el usuario %s.", user.pk)

    def authenticate_with_otp(
        self,
        *,
        email: str,
        code: str,
        client_ip: str | None = None,
    ) -> User:
        """Valida el código y devuelve el usuario habilitado asociado al correo."""
        normalized = email.strip().lower()

        # La verificación se ejecuta siempre, exista o no la cuenta local, para
        # no distinguir ambos casos por el tiempo de respuesta.
        verified = self._otp_provider.verify_code(email=normalized, code=code)
        if not verified:
            raise OtpInvalidError("El código no es válido o ya expiró.")

        user = self._users.by_email(normalized).first()
        if user is None:
            logger.error("Código válido para un correo sin cuenta local. Acceso denegado.")
            raise OtpInvalidError("El código no es válido o ya expiró.")

        if not user.is_active:
            raise AccountInactiveError("La cuenta está deshabilitada.")

        self._otp_cooldown.clear(f"email:{normalized}")
        self._record_login(user, via_otp=True)
        return user

    # -- Internos ----------------------------------------------------------

    @staticmethod
    def _attempt_keys(email: str, client_ip: str | None) -> list[str]:
        """Limita por cuenta y por origen, para frenar tanto la fuerza bruta
        distribuida como el bloqueo malicioso de una cuenta concreta."""
        keys = [f"email:{email}"]
        if client_ip:
            keys.append(f"ip:{client_ip}")
        return keys

    def _assert_not_locked(self, keys: list[str]) -> None:
        for key in keys:
            if self._password_limiter.is_exceeded(key):
                retry_after = self._password_limiter.retry_after_seconds(key)
                logger.warning("Acceso bloqueado por intentos fallidos.")
                raise AccountLockedError(retry_after)

    def _register_failures(self, keys: list[str]) -> None:
        for key in keys:
            self._password_limiter.register(key)

    def _clear_failures(self, keys: list[str]) -> None:
        for key in keys:
            self._password_limiter.reset(key)

    def _record_login(self, user: User, *, via_otp: bool) -> None:
        """Auditoría del último acceso, sin disparar señales ni validaciones."""
        field = "last_otp_login" if via_otp else "last_password_login"
        self._users.filter(pk=user.pk).update(**{field: timezone.now()})


def build_login_service() -> LoginService:
    """Construye el servicio con las dependencias configuradas."""
    return LoginService(
        otp_provider=get_otp_provider(),
        password_limiter=RateLimiter(
            namespace="login-password",
            max_events=settings.LOGIN_MAX_FAILED_ATTEMPTS,
            window_seconds=settings.LOGIN_LOCKOUT_SECONDS,
        ),
        otp_limiter=RateLimiter(
            namespace="otp-request",
            max_events=settings.OTP_MAX_REQUESTS_PER_HOUR,
            window_seconds=OTP_REQUESTS_WINDOW_SECONDS,
        ),
        otp_cooldown=Cooldown(
            namespace="otp-cooldown",
            seconds=settings.OTP_RESEND_COOLDOWN_SECONDS,
        ),
    )

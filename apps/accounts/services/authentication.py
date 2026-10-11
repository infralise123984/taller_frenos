"""
Servicio de autenticación.

Orquesta el acceso con correo y contraseña.

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
    AccountLockedError,
    InvalidCredentialsError,
)
from apps.accounts.models import User
from apps.accounts.services.throttling import RateLimiter

logger = logging.getLogger(__name__)

AuthenticateFn = Callable[..., User | None]


class LoginService:
    """Casos de uso de acceso al sistema."""

    def __init__(
        self,
        *,
        password_limiter: RateLimiter,
        users=User.objects,
        authenticate_fn: AuthenticateFn = authenticate,
    ) -> None:
        self._password_limiter = password_limiter
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
        self._record_login(user)
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

    def _record_login(self, user: User) -> None:
        """Auditoría del último acceso, sin disparar señales ni validaciones."""
        self._users.filter(pk=user.pk).update(last_password_login=timezone.now())


def build_login_service() -> LoginService:
    """Construye el servicio con las dependencias configuradas."""
    return LoginService(
        password_limiter=RateLimiter(
            namespace="login-password",
            max_events=settings.LOGIN_MAX_FAILED_ATTEMPTS,
            window_seconds=settings.LOGIN_LOCKOUT_SECONDS,
        ),
    )

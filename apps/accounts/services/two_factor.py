"""Cifrado, TOTP y casos de uso de autenticación en dos pasos."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import timedelta
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
    TwoFactorInvalidCodeError,
    TwoFactorStateError,
)
from apps.accounts.models import User
from apps.accounts.services.throttling import RateLimiter

TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
TOTP_PENDING_MINUTES = 10
TOTP_ISSUER = "Taller de Frenos"
TOTP_LIMITER_NAMESPACE = "two-factor-sensitive"

AuthenticateFn = authenticate


def _fernet() -> Fernet:
    key = settings.TOTP_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured("Configura TOTP_ENCRYPTION_KEY antes de usar 2FA.")
    try:
        return Fernet(key.encode("ascii"))
    except (UnicodeEncodeError, ValueError) as exc:
        raise ImproperlyConfigured("TOTP_ENCRYPTION_KEY no es una clave Fernet válida.") from exc


def encrypt_totp_secret(secret: str) -> str:
    """Cifra una semilla TOTP; nunca se almacena sin protección."""
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_totp_secret(ciphertext: str) -> str:
    """Descifra una semilla TOTP o falla explícitamente si la clave no coincide."""
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("ascii")
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError) as exc:
        raise ImproperlyConfigured(
            "No se pudo descifrar el secreto 2FA; verifica TOTP_ENCRYPTION_KEY."
        ) from exc


def generate_totp_secret() -> str:
    """Genera una semilla aleatoria de 160 bits codificada en Base32."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_provisioning_uri(*, email: str, secret: str) -> str:
    """Construye el URI estándar que consumen las aplicaciones autenticadoras."""
    label = quote(f"{TOTP_ISSUER}:{email}", safe="")
    issuer = quote(TOTP_ISSUER, safe="")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={issuer}"
        f"&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD_SECONDS}"
    )


def _code_for_counter(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary_code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(binary_code % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def matching_totp_counter(*, secret: str, code: str, timestamp: float | None = None) -> int | None:
    """Acepta la ventana actual ±1 y devuelve el paso coincidente."""
    if len(code) != TOTP_DIGITS or not code.isascii() or not code.isdigit():
        return None

    current_counter = int(
        (timestamp if timestamp is not None else time.time()) // TOTP_PERIOD_SECONDS
    )
    matches = [
        counter
        for counter in range(max(0, current_counter - 1), current_counter + 2)
        if hmac.compare_digest(_code_for_counter(secret, counter), code)
    ]
    return max(matches, default=None)


class TwoFactorService:
    """Administra el estado TOTP, protege las semillas y previene la repetición."""

    def __init__(
        self,
        *,
        limiter: RateLimiter | None = None,
        authenticate_fn: AuthenticateFn = authenticate,
    ) -> None:
        self._limiter = limiter or RateLimiter(
            namespace=TOTP_LIMITER_NAMESPACE,
            max_events=settings.LOGIN_MAX_FAILED_ATTEMPTS,
            window_seconds=settings.LOGIN_LOCKOUT_SECONDS,
        )
        self._authenticate = authenticate_fn

    def begin_setup(self, *, user: User, password: str, client_ip: str | None) -> None:
        """Guarda una semilla cifrada temporal tras revalidar la contraseña."""
        self._verify_password(user=user, password=password, client_ip=client_ip)
        if user.totp_enabled:
            raise TwoFactorStateError("La autenticación en dos pasos ya está activa.")

        user.totp_pending_secret_encrypted = encrypt_totp_secret(generate_totp_secret())
        user.totp_pending_expires_at = timezone.now() + timedelta(minutes=TOTP_PENDING_MINUTES)
        user.save(update_fields=["totp_pending_secret_encrypted", "totp_pending_expires_at"])
        self._clear_failures(user.email, client_ip)

    def pending_secret(self, *, user: User) -> str | None:
        """Devuelve la semilla de configuración solo mientras el reto siga vigente."""
        if not user.totp_pending_secret_encrypted:
            return None
        if user.totp_pending_expires_at is None or user.totp_pending_expires_at <= timezone.now():
            User.objects.filter(pk=user.pk).update(
                totp_pending_secret_encrypted="",
                totp_pending_expires_at=None,
            )
            return None
        return decrypt_totp_secret(user.totp_pending_secret_encrypted)

    def enable(self, *, user: User, password: str, code: str, client_ip: str | None) -> None:
        """Activa 2FA solo después de probar contraseña y semilla recién escaneada."""
        self._verify_password(user=user, password=password, client_ip=client_ip)

        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            secret = self.pending_secret(user=locked_user)
            if secret is None:
                raise TwoFactorStateError("La configuración expiró. Iníciala nuevamente.")

            counter = matching_totp_counter(secret=secret, code=code)
            if counter is None:
                self._register_failure(user.email, client_ip)
                raise TwoFactorInvalidCodeError("El código no es válido.")

            locked_user.totp_secret_encrypted = locked_user.totp_pending_secret_encrypted
            locked_user.totp_pending_secret_encrypted = ""
            locked_user.totp_pending_expires_at = None
            # El código que confirma la configuración no se marca como consumido
            # para el login: la misma ventana sigue vigente unos segundos y la
            # persona la reutiliza al entrar. Solo se registra como piso mínimo
            # para que el login no acepte una ventana anterior a la configurada.
            locked_user.totp_setup_verified_step = counter
            locked_user.totp_last_verified_step = None
            locked_user.totp_enabled = True
            locked_user.save(
                update_fields=[
                    "totp_secret_encrypted",
                    "totp_pending_secret_encrypted",
                    "totp_pending_expires_at",
                    "totp_setup_verified_step",
                    "totp_last_verified_step",
                    "totp_enabled",
                ]
            )
        self._clear_failures(user.email, client_ip)

    def verify_login_code(self, *, user: User, code: str, client_ip: str | None) -> None:
        """Verifica un TOTP activo de un solo uso para completar el login."""
        self._assert_not_locked(self._attempt_keys(user.email, client_ip))
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            if not locked_user.totp_enabled or not locked_user.totp_secret_encrypted:
                raise TwoFactorStateError("La autenticación en dos pasos no está activa.")

            counter = matching_totp_counter(
                secret=decrypt_totp_secret(locked_user.totp_secret_encrypted),
                code=code,
            )
            self._consume_counter(
                user=locked_user,
                counter=counter,
                email=user.email,
                client_ip=client_ip,
            )
        self._clear_failures(user.email, client_ip)

    def disable(self, *, user: User, password: str, code: str, client_ip: str | None) -> None:
        """Desactiva 2FA solo tras confirmar la contraseña y un código vigente."""
        self._verify_password(user=user, password=password, client_ip=client_ip)

        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            if not locked_user.totp_enabled or not locked_user.totp_secret_encrypted:
                raise TwoFactorStateError("La autenticación en dos pasos ya está desactivada.")

            counter = matching_totp_counter(
                secret=decrypt_totp_secret(locked_user.totp_secret_encrypted),
                code=code,
            )
            self._consume_counter(
                user=locked_user,
                counter=counter,
                email=user.email,
                client_ip=client_ip,
            )
            locked_user.totp_enabled = False
            locked_user.totp_secret_encrypted = ""
            locked_user.totp_pending_secret_encrypted = ""
            locked_user.totp_pending_expires_at = None
            locked_user.totp_last_verified_step = None
            locked_user.totp_setup_verified_step = None
            locked_user.save(
                update_fields=[
                    "totp_enabled",
                    "totp_secret_encrypted",
                    "totp_pending_secret_encrypted",
                    "totp_pending_expires_at",
                    "totp_last_verified_step",
                    "totp_setup_verified_step",
                ]
            )
        self._clear_failures(user.email, client_ip)

    def _verify_password(self, *, user: User, password: str, client_ip: str | None) -> None:
        keys = self._attempt_keys(user.email, client_ip)
        self._assert_not_locked(keys)
        authenticated = self._authenticate(username=user.email, password=password)
        if authenticated is None or authenticated.pk != user.pk:
            self._register_failures(user.email, client_ip)
            raise InvalidCredentialsError("Correo o contraseña incorrectos.")

    def _consume_counter(
        self,
        *,
        user: User,
        counter: int | None,
        email: str,
        client_ip: str | None,
    ) -> None:
        if counter is None:
            self._register_failure(email, client_ip)
            raise TwoFactorInvalidCodeError("El código no es válido.")

        # Tras activar 2FA el paso de configuración actúa como piso: la ventana
        # que lo confirmó todavía puede usarse una vez para entrar, pero una
        # ventana anterior ya no es admisible.
        setup_step = user.totp_setup_verified_step
        if setup_step is not None and counter < setup_step:
            self._register_failure(email, client_ip)
            raise TwoFactorInvalidCodeError("El código no es válido o ya fue utilizado.")

        accepted = (
            User.objects.filter(pk=user.pk)
            .filter(
                Q(totp_last_verified_step__lt=counter) | Q(totp_last_verified_step__isnull=True)
            )
            .update(totp_last_verified_step=counter, totp_setup_verified_step=None)
        )
        if accepted != 1:
            self._register_failure(email, client_ip)
            raise TwoFactorInvalidCodeError("El código ya fue utilizado.")

    def _assert_not_locked(self, keys: list[str]) -> None:
        for key in keys:
            if self._limiter.is_exceeded(key):
                raise AccountLockedError(self._limiter.retry_after_seconds(key))

    def _register_failure(self, email: str, client_ip: str | None) -> None:
        for key in self._attempt_keys(email, client_ip):
            self._limiter.register(key)

    def _register_failures(self, email: str, client_ip: str | None) -> None:
        self._register_failure(email, client_ip)

    def _clear_failures(self, email: str, client_ip: str | None) -> None:
        for key in self._attempt_keys(email, client_ip):
            self._limiter.reset(key)

    @staticmethod
    def _attempt_keys(email: str, client_ip: str | None) -> list[str]:
        keys = [f"email:{email.strip().lower()}"]
        if client_ip:
            keys.append(f"ip:{client_ip}")
        return keys


def build_two_factor_service() -> TwoFactorService:
    """Construye el servicio con el limitador de intentos configurado."""
    return TwoFactorService()

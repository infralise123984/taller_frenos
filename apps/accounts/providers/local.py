"""
Proveedor de OTP que vive dentro de Django.

Se usa en desarrollo y en pruebas: no requiere credenciales externas. El código
se genera con ``secrets``, se almacena hasheado y se invalida al primer uso
exitoso, al expirar o al agotar los intentos permitidos.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.accounts.emails import send_otp_email
from apps.accounts.exceptions import OtpDeliveryError
from apps.accounts.models import OtpChallenge
from apps.accounts.providers.base import OtpProvider

logger = logging.getLogger(__name__)

OtpSender = Callable[..., None]


class LocalOtpProvider(OtpProvider):
    """Genera, persiste (hasheado) y valida los códigos dentro de la base local."""

    def __init__(
        self,
        *,
        code_length: int,
        ttl_seconds: int,
        max_attempts: int,
        sender: OtpSender = send_otp_email,
    ) -> None:
        self._code_length = code_length
        self._ttl_seconds = ttl_seconds
        self._max_attempts = max_attempts
        self._sender = sender

    # -- Envío -------------------------------------------------------------

    def send_code(self, *, email: str, request_ip: str | None = None) -> None:
        normalized = self._normalize(email)
        raw_code = self._generate_code()

        # Un correo solo puede tener un código vigente: al emitir uno nuevo se
        # invalida el anterior.
        OtpChallenge.invalidate_pending(normalized)
        challenge = OtpChallenge.objects.create(
            email=normalized,
            code_hash=make_password(raw_code),
            expires_at=timezone.now() + timedelta(seconds=self._ttl_seconds),
            max_attempts=self._max_attempts,
            request_ip=request_ip,
        )

        try:
            self._sender(email=normalized, code=raw_code, ttl_seconds=self._ttl_seconds)
        except Exception as exc:  # noqa: BLE001 - se traduce a error de dominio
            logger.exception("Fallo al enviar el código de acceso (desafío %s).", challenge.pk)
            raise OtpDeliveryError("No se pudo enviar el código de acceso.") from exc

    # -- Verificación ------------------------------------------------------

    def verify_code(self, *, email: str, code: str) -> bool:
        normalized = self._normalize(email)
        candidate = code.strip()

        # Un código mal formado nunca puede ser correcto, así que no se
        # contabiliza como intento (evita autobloqueos por un error de tipeo).
        if not self._has_valid_format(candidate):
            return False

        with transaction.atomic():
            challenge = (
                OtpChallenge.objects.select_for_update()
                .for_email(normalized)
                .filter(consumed_at__isnull=True)
                .order_by("-created_at")
                .first()
            )
            if challenge is None or not challenge.is_usable:
                return False

            if not check_password(candidate, challenge.code_hash):
                challenge.register_failed_attempt()
                logger.info("Código OTP incorrecto para un desafío vigente.")
                return False

            challenge.consume()
            return True

    # -- Internos ----------------------------------------------------------

    @staticmethod
    def _normalize(email: str) -> str:
        return email.strip().lower()

    def _generate_code(self) -> str:
        """Código numérico criptográficamente seguro, con ceros a la izquierda."""
        upper_bound = 10**self._code_length
        return f"{secrets.randbelow(upper_bound):0{self._code_length}d}"

    def _has_valid_format(self, code: str) -> bool:
        return len(code) == self._code_length and code.isdigit()

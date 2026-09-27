"""
Proveedor de OTP delegado a Supabase Auth.

Flujo híbrido: Supabase se encarga de generar, enviar y validar el código por
correo; Django sigue siendo la fuente de verdad de usuarios, roles y sesiones.
Django solo emite su propia sesión cuando Supabase confirma el código.
"""

from __future__ import annotations

import logging

import httpx

from apps.accounts.exceptions import OtpDeliveryError, OtpVerificationUnavailableError
from apps.accounts.providers.base import OtpProvider

logger = logging.getLogger(__name__)

# Códigos que Supabase devuelve cuando el código es inválido o expiró. Se
# traducen a "código incorrecto", no a un fallo de infraestructura.
_REJECTION_STATUS_CODES = frozenset({400, 401, 403, 404, 422})


class SupabaseOtpProvider(OtpProvider):
    """Cliente HTTP delgado sobre los endpoints de Auth de Supabase."""

    def __init__(
        self,
        *,
        base_url: str,
        anon_key: str,
        timeout_seconds: float = 10.0,
        create_user: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        self._create_user = create_user
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            headers={
                "apikey": anon_key,
                "Authorization": f"Bearer {anon_key}",
                "Content-Type": "application/json",
            },
        )

    def send_code(self, *, email: str, request_ip: str | None = None) -> None:
        try:
            response = self._client.post(
                "/auth/v1/otp",
                json={"email": email.strip().lower(), "create_user": self._create_user},
            )
        except httpx.HTTPError as exc:
            logger.exception("Error de red al solicitar el OTP a Supabase.")
            raise OtpDeliveryError("No se pudo enviar el código de acceso.") from exc

        if response.status_code >= 400:
            # No se registra el cuerpo completo: podría contener detalles del proyecto.
            logger.warning("Supabase rechazó el envío de OTP (status=%s).", response.status_code)
            raise OtpDeliveryError("No se pudo enviar el código de acceso.")

    def verify_code(self, *, email: str, code: str) -> bool:
        try:
            response = self._client.post(
                "/auth/v1/verify",
                json={
                    "email": email.strip().lower(),
                    "token": code.strip(),
                    "type": "email",
                },
            )
        except httpx.HTTPError as exc:
            logger.exception("Error de red al verificar el OTP con Supabase.")
            raise OtpVerificationUnavailableError(
                "No fue posible verificar el código en este momento."
            ) from exc

        if response.status_code in _REJECTION_STATUS_CODES:
            logger.info("Supabase rechazó el código (status=%s).", response.status_code)
            return False

        if response.status_code >= 400:
            raise OtpVerificationUnavailableError(
                "No fue posible verificar el código en este momento."
            )

        payload = response.json()
        return bool(payload.get("access_token"))

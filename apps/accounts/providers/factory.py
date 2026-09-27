"""
Selección del proveedor de OTP según configuración.

Punto único de decisión (Principio Abierto/Cerrado): agregar un proveedor nuevo
consiste en implementar ``OtpProvider`` y registrar su construcción aquí.
"""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.accounts.providers.base import OtpProvider
from apps.accounts.providers.local import LocalOtpProvider
from apps.accounts.providers.supabase import SupabaseOtpProvider

LOCAL = "local"
SUPABASE = "supabase"


def _build_local() -> OtpProvider:
    return LocalOtpProvider(
        code_length=settings.OTP_CODE_LENGTH,
        ttl_seconds=settings.OTP_TTL_SECONDS,
        max_attempts=settings.OTP_MAX_ATTEMPTS,
    )


def _build_supabase() -> OtpProvider:
    if not (settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY):
        raise ImproperlyConfigured(
            "OTP_PROVIDER=supabase requiere SUPABASE_URL y SUPABASE_ANON_KEY."
        )
    return SupabaseOtpProvider(
        base_url=settings.SUPABASE_URL,
        anon_key=settings.SUPABASE_ANON_KEY,
        timeout_seconds=settings.SUPABASE_TIMEOUT_SECONDS,
        create_user=settings.SUPABASE_OTP_CREATE_USER,
    )


_BUILDERS = {
    LOCAL: _build_local,
    SUPABASE: _build_supabase,
}


@lru_cache(maxsize=1)
def get_otp_provider() -> OtpProvider:
    """Devuelve la instancia compartida del proveedor configurado."""
    name = str(settings.OTP_PROVIDER).strip().lower()
    try:
        builder = _BUILDERS[name]
    except KeyError as exc:
        raise ImproperlyConfigured(
            f"OTP_PROVIDER='{name}' no es válido. Opciones: {sorted(_BUILDERS)}."
        ) from exc
    return builder()


def reset_otp_provider_cache() -> None:
    """Limpia la instancia memorizada. Se usa en pruebas y al cambiar settings."""
    get_otp_provider.cache_clear()

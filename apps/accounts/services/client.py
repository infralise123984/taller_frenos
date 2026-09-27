"""Extracción de datos del cliente HTTP para trazabilidad y limitación de tasa."""

from __future__ import annotations

from django.conf import settings


def get_client_ip(request) -> str | None:
    """
    Devuelve la IP de origen de la petición.

    Por defecto solo se confía en REMOTE_ADDR. Las cabeceras de proxy
    (X-Forwarded-For) solo se consideran si DJANGO_TRUST_PROXY_HEADERS está
    activo, porque de lo contrario cualquier cliente podría falsificarlas y
    evadir los límites de intentos.
    """
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            # La primera entrada es la del cliente original.
            return forwarded.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR") or None

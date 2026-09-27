"""
Normalización de números de teléfono.

El teléfono es el dato con el que se contacta al cliente por WhatsApp, así que
se compara por dígitos para tolerar formatos distintos (+56 9 1234 5678,
9 1234 5678, 56912345678) y evitar duplicar clientes.
"""

from __future__ import annotations

import re

_NON_DIGITS = re.compile(r"\D")

# Prefijo país de Chile. Se agrega solo cuando el número lo requiere.
_COUNTRY_CODE = "56"
_NATIONAL_MOBILE_PREFIX = "9"


def normalize_telefono(raw: str) -> str:
    """
    Devuelve el teléfono en formato canónico de solo dígitos.

    >>> normalize_telefono("+56 9 1234 5678")
    '56912345678'
    >>> normalize_telefono("912345678")
    '56912345678'
    """
    digits = _NON_DIGITS.sub("", raw or "")
    if not digits:
        return ""

    # Número nacional de 9 dígitos (9XXXXXXXX): se le agrega el código de país.
    if len(digits) == 9 and digits.startswith(_NATIONAL_MOBILE_PREFIX):
        return f"{_COUNTRY_CODE}{digits}"

    return digits


def format_telefono(raw: str) -> str:
    """Presentación legible para pantalla, sin alterar el dato almacenado."""
    digits = normalize_telefono(raw)
    if len(digits) == 11 and digits.startswith(f"{_COUNTRY_CODE}{_NATIONAL_MOBILE_PREFIX}"):
        return f"+{_COUNTRY_CODE} {_NATIONAL_MOBILE_PREFIX} {digits[3:7]} {digits[7:]}"
    return raw or ""

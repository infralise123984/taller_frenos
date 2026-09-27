"""
Normalización de patentes.

Función pura y sin dependencias de Django, para poder probarla de forma aislada.
La patente es el eje de búsqueda del sistema, por lo que siempre se almacena
normalizada (mayúsculas, sin espacios ni guiones) y así se busca también.
"""

from __future__ import annotations

import re

_ALLOWED_CHARACTERS = re.compile(r"[^A-Z0-9]")
MAX_LENGTH = 8


def normalize_patente(raw: str) -> str:
    """
    Devuelve la patente lista para almacenar o comparar.

    >>> normalize_patente(" ab-12 34 ")
    'AB1234'
    """
    if not raw:
        return ""
    return _ALLOWED_CHARACTERS.sub("", raw.upper())[:MAX_LENGTH]


def is_valid_patente(raw: str) -> bool:
    """
    Validación de formato, deliberadamente laxa.

    En Chile conviven placas antiguas (BB1234) y nuevas (BBBB12), además de
    vehículos con placas de otras regiones. Por eso se exige solo una mezcla de
    letras y números de largo razonable, sin fijar un patrón rígido que dejaría
    fuera casos legítimos.
    """
    candidate = normalize_patente(raw)
    if not 4 <= len(candidate) <= MAX_LENGTH:
        return False
    return any(char.isalpha() for char in candidate) and any(char.isdigit() for char in candidate)

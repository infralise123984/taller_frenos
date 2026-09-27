"""Filtros de plantilla del taller."""

from __future__ import annotations

from django import template

from apps.workshop.telefonos import format_telefono

register = template.Library()


@register.filter
def telefono_legible(valor: str) -> str:
    """
    Presenta el teléfono almacenado (solo dígitos) en formato local.

    Se resuelve como filtro y no como propiedad del modelo para no mezclar
    presentación con dominio. El valor guardado no cambia: los enlaces a
    WhatsApp siguen usando el número normalizado.
    """
    return format_telefono(valor)

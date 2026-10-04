"""
Clases de presentación compartidas, disponibles para las plantillas.

Los controles que no son campos de un formulario (botones, enlaces, el
selector para agregar líneas) también deben verse igual que el resto del
sistema, y la "voz visual" vive en un solo lugar: :mod:`apps.ui`.
"""

from __future__ import annotations

from django import template

from apps.ui import (
    BOTON_PELIGRO,
    BOTON_PRIMARIO,
    BOTON_QUITAR,
    BOTON_SECUNDARIO,
    INPUT,
    INPUT_COMPACTO,
    SELECT,
    TARJETA,
)

register = template.Library()


@register.simple_tag
def clase_input() -> str:
    return INPUT


@register.simple_tag
def clase_input_compacto() -> str:
    return INPUT_COMPACTO


@register.simple_tag
def clase_select() -> str:
    return SELECT


@register.simple_tag
def clase_tarjeta() -> str:
    return TARJETA


@register.simple_tag
def clase_boton_primario() -> str:
    return BOTON_PRIMARIO


@register.simple_tag
def clase_boton_secundario() -> str:
    return BOTON_SECUNDARIO


@register.simple_tag
def clase_boton_peligro() -> str:
    return BOTON_PELIGRO


@register.simple_tag
def clase_boton_quitar() -> str:
    return BOTON_QUITAR

"""
Servicio de escritura de los datos del taller.

La dirección, la ciudad y el teléfono viven en una fila única que la ficha
impresa lee en cada impresión. Este servicio es el único punto que la modifica,
para que el encabezado no dependa de cómo lo edite el panel de administración.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction

from apps.workshop.models import DatosTaller

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatosTallerEntrada:
    """Datos del encabezado de la ficha, ya validados por el formulario."""

    direccion: str = ""
    ciudad: str = ""
    telefono: str = ""


class ActualizarDatosTallerService:
    """Guarda la fila única del taller; si todavía no existe, la crea."""

    def __init__(self, *, modelo=DatosTaller) -> None:
        self._modelo = modelo

    @transaction.atomic
    def actualizar(self, datos: DatosTallerEntrada) -> DatosTaller:
        taller = self._modelo.get_solo()
        taller.direccion = datos.direccion
        taller.ciudad = datos.ciudad
        taller.telefono = datos.telefono
        taller.save()

        logger.info("Datos del taller actualizados.")
        return taller


def build_actualizar_datos_taller_service() -> ActualizarDatosTallerService:
    """Constructor del servicio con sus dependencias por defecto."""
    return ActualizarDatosTallerService()

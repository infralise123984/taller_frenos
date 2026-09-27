"""Servicios de la app de taller."""

from apps.workshop.services.ingresos import (
    DatosIngreso,
    RegistroIngresoService,
    ResultadoIngreso,
    TrabajoSolicitado,
    build_registro_ingreso_service,
)

__all__ = [
    "DatosIngreso",
    "RegistroIngresoService",
    "ResultadoIngreso",
    "TrabajoSolicitado",
    "build_registro_ingreso_service",
]

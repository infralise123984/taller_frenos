"""
Consultas de lectura del taller.

Estas funciones no modifican estado y concentran los ``select_related`` /
``prefetch_related`` necesarios, para que las vistas y los templates nunca
disparen consultas N+1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db.models import QuerySet

from apps.workshop.models import Cliente, OrdenTrabajo, Vehiculo

LIMITE_BUSQUEDA = 20
LIMITE_INGRESOS_RECIENTES = 8


def buscar_vehiculos(termino: str, *, limite: int = LIMITE_BUSQUEDA) -> QuerySet[Vehiculo]:
    """Vehículos cuya patente coincide con el término, con su dueño precargado."""
    return Vehiculo.objects.with_cliente().buscar(termino)[:limite]


def historial_de_vehiculo(vehiculo: Vehiculo) -> QuerySet[OrdenTrabajo]:
    """Visitas del vehículo, de la más reciente a la más antigua."""
    return OrdenTrabajo.objects.historial_de(vehiculo)


def ingresos_recientes(limite: int = LIMITE_INGRESOS_RECIENTES) -> QuerySet[OrdenTrabajo]:
    """Últimas visitas registradas en el taller."""
    return OrdenTrabajo.objects.recientes(limite)


@dataclass(frozen=True)
class ResumenVehiculo:
    """Datos derivados que se muestran en el encabezado de la ficha."""

    total_visitas: int
    ultima_orden: OrdenTrabajo | None
    proxima_mantencion_km: int | None
    proxima_mantencion_fecha: date | None


def resumen_de_vehiculo(vehiculo: Vehiculo) -> ResumenVehiculo:
    """Consolida el estado del vehículo en dos consultas."""
    total_visitas = vehiculo.ordenes.count()
    ultima_orden = vehiculo.ordenes.order_by("-fecha_ingreso", "-created_at").first()

    return ResumenVehiculo(
        total_visitas=total_visitas,
        ultima_orden=ultima_orden,
        proxima_mantencion_km=ultima_orden.proxima_mantencion_km if ultima_orden else None,
        proxima_mantencion_fecha=ultima_orden.proxima_mantencion_fecha if ultima_orden else None,
    )


def vehiculos_de_cliente(cliente: Cliente) -> QuerySet[Vehiculo]:
    return Vehiculo.objects.with_cliente().filter(cliente=cliente)


def historial_de_cliente(cliente: Cliente, *, limite: int = 10) -> QuerySet[OrdenTrabajo]:
    """Últimas visitas de todos los vehículos del cliente."""
    return (
        OrdenTrabajo.objects.filter(vehiculo__cliente=cliente)
        .with_detalle()
        .order_by("-fecha_ingreso", "-created_at")[:limite]
    )

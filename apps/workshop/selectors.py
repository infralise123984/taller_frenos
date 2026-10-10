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

from apps.workshop.models import Cliente, DatosTaller, OrdenTrabajo, Vehiculo
from apps.workshop.patentes import is_valid_patente, normalize_patente

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


def orden_de_visita(pk: int) -> QuerySet[OrdenTrabajo]:
    """
    Una sola visita con su detalle precargado.

    Lo usan las pantallas de corrección y de impresión de la ficha, que
    necesitan las líneas sin disparar una consulta por línea.
    """
    return OrdenTrabajo.objects.with_detalle().filter(pk=pk)


def datos_del_taller() -> DatosTaller:
    """
    Datos del taller para el encabezado de la ficha impresa.

    Nunca devuelve ``None``: si todavía no se configuraron, entrega una
    instancia vacía y la ficha se imprime sin dirección ni teléfono.
    """
    return DatosTaller.get_solo()


@dataclass(frozen=True)
class VehiculoRegistrado:
    """
    Lo que hace falta saber de una patente que ya está en el sistema.

    Sirve para avisar en el mesón que el auto ya vino, de quién es y cuándo fue
    la última vez, sin obligar a la operadora a volver a la búsqueda.
    """

    vehiculo: Vehiculo
    total_visitas: int
    ultima_orden: OrdenTrabajo | None

    @property
    def cliente(self) -> Cliente:
        return self.vehiculo.cliente

    @property
    def descripcion(self) -> str:
        """Datos del auto para el aviso, con un texto de reemplazo si no hay ninguno."""
        return self.vehiculo.descripcion_corta or "Sin datos de modelo"


def vehiculo_ya_registrado(patente: str) -> VehiculoRegistrado | None:
    """
    El vehículo de esa patente, si ya está registrado.

    Devuelve ``None`` cuando la patente todavía no es un dato confiable (vacía
    o con formato inválido) y cuando el auto es nuevo: en ninguno de los dos
    casos hay algo que avisar. La comparación usa la patente normalizada, así
    que "bjd-f45" encuentra el mismo auto que "BJDF45".

    La última visita se trae con su detalle para poder mostrar qué se le hizo
    sin disparar una consulta por línea.
    """
    normalizada = normalize_patente(patente)
    if not is_valid_patente(normalizada):
        return None

    vehiculo = Vehiculo.objects.with_cliente().filter(patente=normalizada).first()
    if vehiculo is None:
        return None

    return VehiculoRegistrado(
        vehiculo=vehiculo,
        total_visitas=vehiculo.ordenes.count(),
        ultima_orden=vehiculo.ordenes.with_detalle()
        .order_by("-fecha_ingreso", "-created_at")
        .first(),
    )


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

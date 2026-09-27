"""
Servicio de registro de ingresos.

Implementa el caso de uso "llegó un auto": resolver o crear el cliente, resolver
o crear el vehículo, y dejar la visita con sus trabajos en una sola transacción.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction

from apps.workshop.exceptions import IngresoDuplicadoError, PatenteInvalidaError
from apps.workshop.models import Cliente, ItemTrabajo, OrdenTrabajo, Vehiculo
from apps.workshop.patentes import is_valid_patente, normalize_patente
from apps.workshop.telefonos import normalize_telefono

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Contratos de entrada y salida
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrabajoSolicitado:
    """Intervención que se registrará dentro de la visita."""

    tipo: str
    descripcion: str = ""
    repuesto: str = ""


@dataclass(frozen=True)
class DatosIngreso:
    """Datos capturados en el mesón, en una sola pasada."""

    patente: str
    cliente_nombre: str
    cliente_telefono: str
    kilometraje: int
    fecha_ingreso: date
    cliente_email: str = ""
    marca: str = ""
    modelo: str = ""
    anio: int | None = None
    color: str = ""
    observaciones: str = ""
    proxima_mantencion_km: int | None = None
    proxima_mantencion_fecha: date | None = None
    trabajos: tuple[TrabajoSolicitado, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResultadoIngreso:
    """Resultado del registro, con las banderas que la interfaz necesita informar."""

    cliente: Cliente
    vehiculo: Vehiculo
    orden: OrdenTrabajo
    cliente_creado: bool
    vehiculo_creado: bool


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------


class RegistroIngresoService:
    """Registra una visita completa de forma atómica."""

    def __init__(
        self,
        *,
        clientes=Cliente.objects,
        vehiculos=Vehiculo.objects,
        ordenes=OrdenTrabajo.objects,
        items=ItemTrabajo.objects,
    ) -> None:
        self._clientes = clientes
        self._vehiculos = vehiculos
        self._ordenes = ordenes
        self._items = items

    @transaction.atomic
    def registrar(self, datos: DatosIngreso) -> ResultadoIngreso:
        patente = normalize_patente(datos.patente)
        if not is_valid_patente(patente):
            raise PatenteInvalidaError(patente)

        cliente, cliente_creado = self._resolver_cliente(datos)
        vehiculo, vehiculo_creado = self._resolver_vehiculo(patente, cliente, datos)
        self._asegurar_no_duplicado(vehiculo, datos)

        orden = self._crear_orden(vehiculo, datos)
        self._crear_trabajos(orden, datos.trabajos)

        logger.info(
            "Ingreso registrado para la patente %s (visita %s).",
            vehiculo.patente,
            orden.pk,
        )
        return ResultadoIngreso(
            cliente=cliente,
            vehiculo=vehiculo,
            orden=orden,
            cliente_creado=cliente_creado,
            vehiculo_creado=vehiculo_creado,
        )

    # -- Resolución de entidades ------------------------------------------

    def _resolver_cliente(self, datos: DatosIngreso) -> tuple[Cliente, bool]:
        """
        Reutiliza el cliente si su teléfono ya está registrado.

        Se identifica por teléfono y no por nombre porque es el dato estable y
        el que la operadora usa para contactarlo.
        """
        telefono = normalize_telefono(datos.cliente_telefono)
        existente = self._clientes.by_telefono(telefono).first() if telefono else None

        if existente is not None:
            # Se completan datos que hubieran quedado vacíos, sin pisar los ya definidos.
            cambios = []
            if datos.cliente_nombre and existente.nombre != datos.cliente_nombre:
                existente.nombre = datos.cliente_nombre
                cambios.append("nombre")
            if datos.cliente_email and not existente.email:
                existente.email = datos.cliente_email
                cambios.append("email")
            if cambios:
                existente.save(update_fields=[*cambios, "updated_at"])
            return existente, False

        cliente = self._clientes.create(
            nombre=datos.cliente_nombre.strip(),
            telefono=telefono or datos.cliente_telefono.strip(),
            email=datos.cliente_email.strip(),
        )
        return cliente, True

    def _resolver_vehiculo(
        self,
        patente: str,
        cliente: Cliente,
        datos: DatosIngreso,
    ) -> tuple[Vehiculo, bool]:
        """
        Devuelve el vehículo de la patente, creándolo si es la primera visita.

        Si ya existe se conserva su dueño actual: cambiar de propietario es una
        decisión explícita que no debe ocurrir por un registro rápido.
        """
        existente = self._vehiculos.filter(patente=patente).first()
        if existente is not None:
            self._completar_datos_vehiculo(existente, datos)
            return existente, False

        vehiculo = self._vehiculos.create(
            patente=patente,
            cliente=cliente,
            marca=datos.marca.strip(),
            modelo=datos.modelo.strip(),
            anio=datos.anio,
            color=datos.color.strip(),
        )
        return vehiculo, True

    def _completar_datos_vehiculo(self, vehiculo: Vehiculo, datos: DatosIngreso) -> None:
        """Actualiza los datos descriptivos solo cuando llegan valores nuevos."""
        cambios: list[str] = []
        for campo, valor in (
            ("marca", datos.marca.strip()),
            ("modelo", datos.modelo.strip()),
            ("color", datos.color.strip()),
        ):
            if valor and getattr(vehiculo, campo) != valor:
                setattr(vehiculo, campo, valor)
                cambios.append(campo)

        if datos.anio and vehiculo.anio != datos.anio:
            vehiculo.anio = datos.anio
            cambios.append("anio")

        if cambios:
            vehiculo.save(update_fields=[*cambios, "updated_at"])

    # -- Persistencia de la visita ----------------------------------------

    def _asegurar_no_duplicado(self, vehiculo: Vehiculo, datos: DatosIngreso) -> None:
        duplicado = self._ordenes.filter(
            vehiculo=vehiculo,
            fecha_ingreso=datos.fecha_ingreso,
            kilometraje=datos.kilometraje,
        ).first()
        if duplicado is not None:
            logger.warning("Se bloqueó un ingreso duplicado para %s.", vehiculo.patente)
            raise IngresoDuplicadoError(orden_id=duplicado.pk)

    def _crear_orden(self, vehiculo: Vehiculo, datos: DatosIngreso) -> OrdenTrabajo:
        return self._ordenes.create(
            vehiculo=vehiculo,
            fecha_ingreso=datos.fecha_ingreso,
            kilometraje=datos.kilometraje,
            observaciones=datos.observaciones.strip(),
            proxima_mantencion_km=datos.proxima_mantencion_km,
            proxima_mantencion_fecha=datos.proxima_mantencion_fecha,
        )

    def _crear_trabajos(self, orden: OrdenTrabajo, trabajos: tuple[TrabajoSolicitado, ...]) -> None:
        """Crea las intervenciones, descartando tipos repetidos que vengan del formulario."""
        vistos: set[str] = set()
        nuevos = []
        for trabajo in trabajos:
            if trabajo.tipo in vistos:
                continue
            vistos.add(trabajo.tipo)
            nuevos.append(
                ItemTrabajo(
                    orden=orden,
                    tipo=trabajo.tipo,
                    descripcion=trabajo.descripcion.strip()[:250],
                    repuesto=trabajo.repuesto.strip()[:150],
                )
            )

        if nuevos:
            self._items.bulk_create(nuevos)


def build_registro_ingreso_service() -> RegistroIngresoService:
    """Constructor del servicio con sus dependencias por defecto."""
    return RegistroIngresoService()

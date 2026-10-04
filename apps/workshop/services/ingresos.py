"""
Servicios de escritura de fichas de visita.

Aquí viven los dos casos de uso que modifican una visita: registrar un ingreso
(el auto llegó al mesón) y corregir una ficha ya guardada. Ambos comparten las
reglas de las líneas de la ficha, que se validan antes de tocar la base de datos.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction

from apps.workshop.exceptions import (
    FichaVaciaError,
    IngresoDuplicadoError,
    LineaFichaInvalidaError,
    PatenteInvalidaError,
    TotalFichaNegativoError,
)
from apps.workshop.models import (
    TOPE_PRECIO,
    Cliente,
    ItemTrabajo,
    OrdenTrabajo,
    TipoItemFicha,
    Vehiculo,
)
from apps.workshop.patentes import is_valid_patente, normalize_patente
from apps.workshop.telefonos import normalize_telefono

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Contratos de entrada y salida
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineaFicha:
    """Una línea de la ficha: el trabajo, su precio y los datos del repuesto."""

    tipo: str
    precio: int = 0
    detalle: str = ""
    codigo_repuesto: str = ""
    marca_repuesto: str = ""


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
    lineas: tuple[LineaFicha, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResultadoIngreso:
    """Resultado del registro, con las banderas que la interfaz necesita informar."""

    cliente: Cliente
    vehiculo: Vehiculo
    orden: OrdenTrabajo
    cliente_creado: bool
    vehiculo_creado: bool


# ---------------------------------------------------------------------------
# Reglas de las líneas de la ficha
# ---------------------------------------------------------------------------


def validar_lineas(lineas: tuple[LineaFicha, ...]) -> None:
    """
    Comprueba las líneas antes de persistirlas (denegación por defecto).

    Un descuento se escribe con precio negativo; ninguna otra línea puede
    restar, y el total de la ficha nunca puede quedar bajo cero.
    """
    if not lineas:
        raise FichaVaciaError()

    for linea in lineas:
        if linea.tipo not in TipoItemFicha.values:
            raise LineaFichaInvalidaError(f"El trabajo '{linea.tipo}' no existe en el catálogo.")

        if not -TOPE_PRECIO <= linea.precio <= TOPE_PRECIO:
            raise LineaFichaInvalidaError(
                f"El precio de '{linea.tipo}' está fuera del rango permitido."
            )

        if linea.precio < 0 and linea.tipo != TipoItemFicha.DESCUENTO:
            raise LineaFichaInvalidaError(
                f"Solo la línea de descuento puede llevar un monto negativo ('{linea.tipo}')."
            )

    total = sum(linea.precio for linea in lineas)
    if total < 0:
        raise TotalFichaNegativoError(total)


def construir_items(orden: OrdenTrabajo, lineas: tuple[LineaFicha, ...]) -> list[ItemTrabajo]:
    """
    Traduce las líneas del contrato a filas de la base de datos.

    Es una función pura: no guarda nada, para que los servicios decidan cuándo
    persistir.
    """
    return [
        ItemTrabajo(
            orden=orden,
            tipo=linea.tipo,
            detalle=linea.detalle.strip()[:250],
            codigo_repuesto=linea.codigo_repuesto.strip()[:60],
            marca_repuesto=linea.marca_repuesto.strip()[:60],
            precio=linea.precio,
        )
        for linea in lineas
    ]


# ---------------------------------------------------------------------------
# Servicio de registro
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

        validar_lineas(datos.lineas)

        cliente, cliente_creado = self._resolver_cliente(datos)
        vehiculo, vehiculo_creado = self._resolver_vehiculo(patente, cliente, datos)
        self._asegurar_no_duplicado(vehiculo, datos)

        orden = self._crear_orden(vehiculo, datos)
        self._crear_lineas(orden, datos.lineas)

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

    def _crear_lineas(self, orden: OrdenTrabajo, lineas: tuple[LineaFicha, ...]) -> None:
        """Crea las líneas de la ficha, respetando el orden en que se agregaron."""
        self._items.bulk_create(construir_items(orden, lineas))


# ---------------------------------------------------------------------------
# Servicio de corrección de una ficha guardada
# ---------------------------------------------------------------------------


class ActualizarFichaService:
    """
    Corrige las líneas y las observaciones de una visita ya registrada.

    No toca el vehículo, el dueño, la fecha ni el kilometraje: para eso está el
    registro de un ingreso nuevo. Las líneas se reemplazan en una transacción,
    de modo que la ficha nunca queda a medio corregir.
    """

    def __init__(self, *, items=ItemTrabajo.objects) -> None:
        self._items = items

    @transaction.atomic
    def actualizar(
        self,
        orden: OrdenTrabajo,
        *,
        lineas: tuple[LineaFicha, ...],
        observaciones: str = "",
    ) -> OrdenTrabajo:
        validar_lineas(lineas)

        orden.observaciones = observaciones.strip()
        orden.save(update_fields=["observaciones", "updated_at"])

        self._items.filter(orden=orden).delete()
        self._items.bulk_create(construir_items(orden, lineas))

        logger.info("Ficha de la visita %s corregida.", orden.pk)
        return orden


def build_registro_ingreso_service() -> RegistroIngresoService:
    """Constructor del servicio con sus dependencias por defecto."""
    return RegistroIngresoService()


def build_actualizar_ficha_service() -> ActualizarFichaService:
    """Constructor del servicio de corrección con sus dependencias por defecto."""
    return ActualizarFichaService()

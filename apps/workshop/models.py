"""
Modelos de la gestión del taller.

El eje del sistema es la patente del vehículo: a partir de ella se llega al
dueño y a todo el historial de intervenciones.
"""

from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.workshop.patentes import normalize_patente
from apps.workshop.telefonos import normalize_telefono

# ---------------------------------------------------------------------------
# Clientes y vehículos
# ---------------------------------------------------------------------------


class ClienteQuerySet(models.QuerySet):
    """Consultas reutilizables sobre clientes."""

    def by_telefono(self, telefono: str):
        """Busca por teléfono normalizado, tolerando distintos formatos."""
        normalized = normalize_telefono(telefono)
        if not normalized:
            return self.none()
        return self.filter(telefono=normalized)

    def with_vehiculos(self):
        return self.prefetch_related("vehiculos")


class Cliente(models.Model):
    """Dueño de uno o más vehículos atendidos en el taller."""

    nombre = models.CharField("nombre", max_length=150)
    telefono = models.CharField(
        "teléfono / WhatsApp",
        max_length=32,
        help_text="Número al que se avisa cuando el vehículo está listo.",
    )
    email = models.EmailField("correo", blank=True)
    notas = models.TextField("notas", blank=True)
    created_at = models.DateTimeField("creado el", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado el", auto_now=True)

    objects = ClienteQuerySet.as_manager()

    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["nombre"], name="cliente_nombre_idx"),
            models.Index(fields=["telefono"], name="cliente_telefono_idx"),
        ]

    def __str__(self) -> str:
        return self.nombre

    # Efecto secundario explícito: el teléfono se guarda en formato canónico
    # para que la detección de clientes repetidos sea confiable.
    def save(self, *args, **kwargs):
        self.telefono = normalize_telefono(self.telefono)
        return super().save(*args, **kwargs)

    @property
    def cantidad_vehiculos(self) -> int:
        return self.vehiculos.count()


class VehiculoQuerySet(models.QuerySet):
    """Consultas reutilizables sobre vehículos."""

    def with_cliente(self):
        """Incluye al dueño en la misma consulta (evita N+1 en las fichas)."""
        return self.select_related("cliente")

    def buscar(self, termino: str):
        """
        Busca por patente parcial o completa.

        Los resultados con coincidencia exacta se ordenan primero, porque es el
        caso habitual: la operadora escribe la patente completa.
        """
        normalized = normalize_patente(termino)
        if not normalized:
            return self.none()

        return (
            self.filter(patente__icontains=normalized)
            .annotate(
                coincidencia_exacta=models.Case(
                    models.When(patente=normalized, then=models.Value(0)),
                    default=models.Value(1),
                    output_field=models.IntegerField(),
                )
            )
            .order_by("coincidencia_exacta", "patente")
        )


class Vehiculo(models.Model):
    """Vehículo identificado por su patente."""

    patente = models.CharField("patente", max_length=8, unique=True, db_index=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="vehiculos",
        verbose_name="dueño",
    )
    marca = models.CharField("marca", max_length=60, blank=True)
    modelo = models.CharField("modelo", max_length=60, blank=True)
    anio = models.PositiveSmallIntegerField(
        "año",
        null=True,
        blank=True,
        validators=[MinValueValidator(1900)],
    )
    color = models.CharField("color", max_length=40, blank=True)
    notas = models.TextField("notas", blank=True)
    created_at = models.DateTimeField("creado el", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado el", auto_now=True)

    objects = VehiculoQuerySet.as_manager()

    class Meta:
        verbose_name = "vehículo"
        verbose_name_plural = "vehículos"
        ordering = ["patente"]

    def __str__(self) -> str:
        return self.patente

    # Efecto secundario explícito: la patente se normaliza antes de persistir
    # para que la búsqueda nunca dependa del formato con que se escribió.
    def save(self, *args, **kwargs):
        self.patente = normalize_patente(self.patente)
        return super().save(*args, **kwargs)

    @property
    def descripcion_corta(self) -> str:
        """Texto legible para listados: 'Toyota Yaris 2019' o un guion si falta todo."""
        partes = [parte for parte in (self.marca, self.modelo) if parte]
        if self.anio:
            partes.append(str(self.anio))
        return " ".join(partes) if partes else "Sin datos de modelo"

    @property
    def ultima_orden(self) -> OrdenTrabajo | None:
        return self.ordenes.first()


# ---------------------------------------------------------------------------
# Órdenes de trabajo e intervenciones
# ---------------------------------------------------------------------------


class TipoTrabajo(models.TextChoices):
    """Catálogo de trabajos de frenos que realiza el taller."""

    CAMBIO_PASTILLAS = "cambio_pastillas", "Cambio de pastillas"
    CAMBIO_DISCOS = "cambio_discos", "Cambio de discos"
    RECTIFICADO_DISCOS = "rectificado_discos", "Rectificado de discos"
    CAMBIO_LIQUIDO = "cambio_liquido", "Cambio de líquido de frenos"
    PURGA = "purga", "Purga de frenos"
    REPARACION_CALIPERS = "reparacion_calipers", "Reparación de cálipers"
    REVISION = "revision", "Revisión / diagnóstico"
    OTRO = "otro", "Otro trabajo"


class OrdenTrabajoQuerySet(models.QuerySet):
    """Consultas reutilizables sobre órdenes de trabajo."""

    def with_detalle(self):
        """Trae vehículo, dueño e intervenciones en tres consultas fijas."""
        return self.select_related("vehiculo", "vehiculo__cliente").prefetch_related("items")

    def historial_de(self, vehiculo: Vehiculo):
        """Historial cronológico descendente de un vehículo."""
        return (
            self.filter(vehiculo=vehiculo).with_detalle().order_by("-fecha_ingreso", "-created_at")
        )

    def recientes(self, limite: int = 8):
        """Últimas visitas por fecha de ingreso, no por orden de digitación."""
        return self.with_detalle().order_by("-fecha_ingreso", "-created_at")[:limite]


class OrdenTrabajo(models.Model):
    """
    Una visita al taller: cuándo vino el vehículo, con qué kilometraje y qué se hizo.
    """

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.PROTECT,
        related_name="ordenes",
        verbose_name="vehículo",
    )
    fecha_ingreso = models.DateField("fecha de ingreso", default=timezone.localdate)
    kilometraje = models.PositiveIntegerField(
        "kilometraje",
        validators=[MinValueValidator(0)],
        help_text="Kilometraje que marcaba el vehículo al ingresar.",
    )
    observaciones = models.TextField("observaciones", blank=True)
    proxima_mantencion_km = models.PositiveIntegerField(
        "próxima mantención (km)",
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    proxima_mantencion_fecha = models.DateField(
        "próxima mantención (fecha)",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("registrada el", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada el", auto_now=True)

    objects = OrdenTrabajoQuerySet.as_manager()

    class Meta:
        verbose_name = "orden de trabajo"
        verbose_name_plural = "órdenes de trabajo"
        ordering = ["-fecha_ingreso", "-created_at"]
        indexes = [
            models.Index(fields=["vehiculo", "-fecha_ingreso"], name="orden_vehiculo_fecha_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.vehiculo.patente} · {self.fecha_ingreso:%d-%m-%Y}"

    @property
    def resumen_trabajos(self) -> str:
        """Lista legible de las intervenciones realizadas, para los listados."""
        tipos = [item.get_tipo_display() for item in self.items.all()]
        return ", ".join(tipos) if tipos else "Sin detalle registrado"

    @property
    def tiene_proxima_mantencion(self) -> bool:
        return bool(self.proxima_mantencion_km or self.proxima_mantencion_fecha)


class ItemTrabajo(models.Model):
    """Intervención puntual dentro de una orden de trabajo."""

    orden = models.ForeignKey(
        OrdenTrabajo,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="orden",
    )
    tipo = models.CharField("tipo de trabajo", max_length=32, choices=TipoTrabajo.choices)
    descripcion = models.CharField("detalle", max_length=250, blank=True)
    repuesto = models.CharField("repuesto utilizado", max_length=150, blank=True)
    created_at = models.DateTimeField("registrado el", auto_now_add=True)

    class Meta:
        verbose_name = "trabajo realizado"
        verbose_name_plural = "trabajos realizados"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["orden", "tipo"], name="item_orden_tipo_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} ({self.orden})"

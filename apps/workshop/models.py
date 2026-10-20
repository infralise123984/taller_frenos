"""
Modelos de la gestión del taller.

El eje del sistema es la patente del vehículo: a partir de ella se llega al
dueño y a todo el historial de intervenciones. Cada visita guarda sus líneas
de ficha con precio, y el total de la visita es la suma de esas líneas.
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
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

    nombre = models.CharField("nombre", max_length=150, blank=True)
    telefono = models.CharField(
        "teléfono / WhatsApp",
        max_length=32,
        blank=True,
        help_text="Opcional. Número para avisar cuando el vehículo está listo.",
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
        return self.nombre or "Cliente sin nombre"

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
        """Datos descriptivos conocidos del vehículo, si existen."""
        partes = [parte for parte in (self.marca, self.modelo) if parte]
        if self.anio:
            partes.append(str(self.anio))
        return " ".join(partes)

    @property
    def ultima_orden(self) -> OrdenTrabajo | None:
        return self.ordenes.first()


# ---------------------------------------------------------------------------
# Órdenes de trabajo e intervenciones
# ---------------------------------------------------------------------------


# Tope de una línea de la ficha. Es simétrico: el mismo monto máximo para un
# trabajo y para un descuento. Evita que un error de tipeo (un cero de más)
# arruine el total de la visita.
TOPE_PRECIO = 10_000_000


class TipoItemFicha(models.TextChoices):
    """
    Catálogo de líneas de la ficha de trabajo.

    Reproduce las 15 líneas impresas de la ficha de papel, más
    ``DISCOS_NUEVOS``, ``CILINDROS_NUEVOS`` y dos opciones de servicio:
    ``DESCUENTO`` (se escribe con precio negativo) y ``OTRO`` (para lo que no
    está en la lista).
    """

    PASTILLAS = "pastillas", "Pastillas"
    RECT_DISCO = "rect_disco", "Rect. Disco"
    DISCOS_NUEVOS = "discos_nuevos", "Discos nuevos"
    PATINES = "patines", "Patines"
    RECT_TAMBORES = "rect_tambores", "Rect. Tambores"
    CILINDROS_NUEVOS = "cilindros_nuevos", "Cilindros nuevos"
    GOMAS_CILINDROS = "gomas_cilindros", "Gomas Cilindros"
    LIQUIDO = "liquido", "Líquido"
    SEGURO_PASTILLAS = "seguro_pastillas", "Seguro Pastillas"
    REP_BOMBA = "rep_bomba", "Rep. Bomba"
    KIT_BOMBA = "kit_bomba", "Kit Bomba"
    INST_PIOLA = "inst_piola", "Inst. Piola F/Mano"
    FLEXIBLE = "flexible", "Flexible"
    RESORTE_PATIN = "resorte_patin", "Resorte Patín"
    REP_CALIPER = "rep_caliper", "Rep. Caliper"
    REGULACION_TRAS = "regulacion_tras", "Regulación Tras."
    OBRA_MANO = "obra_mano", "Obra de Mano"
    DESCUENTO = "descuento", "Descuento"
    OTRO = "otro", "Otro (escribir en el detalle)"


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
    Una visita al taller: cuándo vino el vehículo y qué se hizo.
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
        null=True,
        blank=True,
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
    def total(self) -> int:
        """
        Suma de las líneas de la ficha, en pesos.

        Se calcula al leer y no se guarda en la base de datos: un total
        almacenado puede quedar desincronizado de sus líneas. Los descuentos
        restan solos, porque su precio es negativo. Los listados ya precargan
        las líneas (``with_detalle`` en los selectores), así que esto no
        dispara consultas adicionales.
        """
        return sum(item.precio for item in self.items.all())

    @property
    def tiene_proxima_mantencion(self) -> bool:
        return bool(self.proxima_mantencion_km or self.proxima_mantencion_fecha)


class ItemTrabajo(models.Model):
    """Línea de la ficha: un trabajo puntual dentro de una orden."""

    orden = models.ForeignKey(
        OrdenTrabajo,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="orden",
    )
    tipo = models.CharField("trabajo", max_length=32, choices=TipoItemFicha.choices)
    detalle = models.CharField(
        "detalle",
        max_length=250,
        blank=True,
        help_text="Texto libre: posición del trabajo (delantero, trasero), observación, etc.",
    )
    codigo_repuesto = models.CharField("código del repuesto", max_length=60, blank=True)
    marca_repuesto = models.CharField("marca del repuesto", max_length=60, blank=True)
    precio = models.IntegerField(
        "precio",
        default=0,
        validators=[
            MinValueValidator(-TOPE_PRECIO),
            MaxValueValidator(TOPE_PRECIO),
        ],
        help_text="Pesos chilenos. Negativo solo en la línea de descuento.",
    )
    created_at = models.DateTimeField("registrado el", auto_now_add=True)

    class Meta:
        verbose_name = "línea de la ficha"
        verbose_name_plural = "líneas de la ficha"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["orden", "tipo"], name="item_orden_tipo_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} ({self.orden})"

    @property
    def es_descuento(self) -> bool:
        return self.tipo == TipoItemFicha.DESCUENTO


# ---------------------------------------------------------------------------
# Datos del taller
# ---------------------------------------------------------------------------


class DatosTaller(models.Model):
    """
    Datos del taller que se imprimen en la ficha entregada al cliente.

    Es una fila única: el taller tiene una sola dirección y un solo teléfono.
    El nombre y el rubro no se guardan aquí porque no cambian y viven como
    título fijo de la plantilla de impresión.
    """

    direccion = models.CharField("dirección", max_length=200, blank=True)
    ciudad = models.CharField("ciudad", max_length=80, blank=True)
    telefono = models.CharField(
        "teléfono",
        max_length=32,
        blank=True,
        help_text="Tal como debe salir impreso, por ejemplo 225 384 512.",
    )
    actualizado_el = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        verbose_name = "datos del taller"
        verbose_name_plural = "datos del taller"

    def __str__(self) -> str:
        return self.direccion or "Datos del taller"

    # Efecto secundario explícito: fuerza la fila única (pk=1) para que no
    # puedan coexistir dos encabezados distintos.
    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls) -> DatosTaller:
        """La única fila; si todavía no existe, una instancia vacía."""
        return cls.objects.first() or cls()

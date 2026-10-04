"""
Vistas de la gestión del taller.

Todas las vistas exigen sesión iniciada: la política se aplica de forma global
con ``LoginRequiredMiddleware`` (denegación por defecto), por lo que no se
repite el decorador en cada función.

Estas vistas solo traducen HTTP ↔ dominio: validan formularios, invocan
selectores o servicios y eligen la plantilla.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.workshop.exceptions import (
    IngresoDuplicadoError,
    PatenteInvalidaError,
    WorkshopDomainError,
)
from apps.workshop.forms import (
    PREFIJO_LINEAS,
    BuscarPatenteForm,
    FichaEdicionForm,
    IngresoRapidoForm,
    LineaFichaFormSet,
    lineas_desde_formset,
    lineas_iniciales,
)
from apps.workshop.models import Cliente, TipoItemFicha, Vehiculo
from apps.workshop.patentes import normalize_patente
from apps.workshop.selectors import (
    buscar_vehiculos,
    datos_del_taller,
    historial_de_cliente,
    historial_de_vehiculo,
    ingresos_recientes,
    orden_de_visita,
    resumen_de_vehiculo,
    vehiculos_de_cliente,
)
from apps.workshop.services import (
    DatosIngreso,
    LineaFicha,
    build_actualizar_ficha_service,
    build_registro_ingreso_service,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pantalla principal: buscar por patente
# ---------------------------------------------------------------------------


def buscar(request: HttpRequest) -> HttpResponse:
    """
    Pantalla de inicio del taller.

    Sin parámetros muestra los últimos ingresos; con ``?patente=`` lista las
    coincidencias. Se resuelve con GET para que el resultado sea un enlace
    compartible y el botón "atrás" del navegador funcione como se espera.
    """
    form = BuscarPatenteForm(request.GET or None)
    termino = ""
    resultados: list[Vehiculo] = []

    if request.GET and form.is_valid():
        termino = form.cleaned_data["patente"]
        resultados = list(buscar_vehiculos(termino))
        if not resultados:
            messages.info(
                request,
                f"No hay ningún vehículo con la patente {termino}. Puedes registrarlo ahora.",
            )

    contexto = {
        "form": form,
        "termino": termino,
        "resultados": resultados,
        "hubo_busqueda": bool(termino),
        "ingresos_recientes": ingresos_recientes(),
    }
    return render(request, "workshop/buscar.html", contexto)


# ---------------------------------------------------------------------------
# Ficha del vehículo y del cliente
# ---------------------------------------------------------------------------


def vehiculo_detail(request: HttpRequest, patente: str) -> HttpResponse:
    """Ficha del vehículo con todo su historial de visitas."""
    vehiculo = get_object_or_404(
        Vehiculo.objects.with_cliente(),
        patente=normalize_patente(patente),
    )

    contexto = {
        "vehiculo": vehiculo,
        "resumen": resumen_de_vehiculo(vehiculo),
        "historial": historial_de_vehiculo(vehiculo),
    }
    return render(request, "workshop/vehiculo_detail.html", contexto)


def cliente_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Ficha del cliente con sus vehículos y sus últimas visitas."""
    cliente = get_object_or_404(Cliente, pk=pk)

    contexto = {
        "cliente": cliente,
        "vehiculos": vehiculos_de_cliente(cliente),
        "historial": historial_de_cliente(cliente),
    }
    return render(request, "workshop/cliente_detail.html", contexto)


# ---------------------------------------------------------------------------
# Registro rápido de un ingreso
# ---------------------------------------------------------------------------


def ingreso_create(request: HttpRequest) -> HttpResponse:
    """Registra cliente, vehículo y la ficha del trabajo, en una sola pasada."""
    inicial = {}
    patente_precargada = (request.GET.get("patente") or "").strip().upper()
    if patente_precargada:
        inicial["patente"] = patente_precargada

    if request.method == "POST":
        form = IngresoRapidoForm(request.POST)
        formset = LineaFichaFormSet(request.POST, prefix=PREFIJO_LINEAS)
        if form.is_valid() and formset.is_valid():
            return _registrar_ingreso(request, form, formset)
    else:
        form = IngresoRapidoForm(initial=inicial)
        formset = LineaFichaFormSet(prefix=PREFIJO_LINEAS)

    return _render_ingreso(request, form, formset)


def _render_ingreso(
    request: HttpRequest,
    form: IngresoRapidoForm,
    formset: LineaFichaFormSet,
) -> HttpResponse:
    contexto = {"form": form, "formset": formset, "catalogo": TipoItemFicha.choices}
    return render(request, "workshop/ingreso_form.html", contexto)


def _registrar_ingreso(
    request: HttpRequest,
    form: IngresoRapidoForm,
    formset: LineaFichaFormSet,
) -> HttpResponse:
    try:
        resultado = build_registro_ingreso_service().registrar(
            _datos_desde_formulario(form, formset)
        )
    except PatenteInvalidaError as exc:
        form.add_error("patente", str(exc))
        return _render_ingreso(request, form, formset)
    except IngresoDuplicadoError:
        messages.warning(
            request,
            "Este vehículo ya tiene un ingreso con la misma fecha y kilometraje. "
            "Te mostramos el registro existente.",
        )
        return redirect("workshop:vehiculo", patente=form.cleaned_data["patente"])
    except WorkshopDomainError as exc:
        # El formulario ya valida estas reglas; aquí solo se evita un error 500
        # si alguna se cuela (por ejemplo, desde una petición manipulada).
        logger.warning("Ingreso rechazado por el dominio: %s", exc)
        form.add_error(None, str(exc))
        return _render_ingreso(request, form, formset)

    mensaje = (
        "Vehículo registrado correctamente."
        if resultado.vehiculo_creado
        else f"Nueva visita agregada para {resultado.vehiculo.patente}."
    )
    if resultado.cliente_creado:
        mensaje = f"{mensaje} Se creó la ficha del cliente."
    messages.success(request, mensaje)

    return redirect("workshop:vehiculo", patente=resultado.vehiculo.patente)


def _datos_desde_formulario(
    form: IngresoRapidoForm,
    formset: LineaFichaFormSet,
) -> DatosIngreso:
    """
    Traduce el formulario al contrato del servicio.

    Se mantiene aparte para que el dominio no conozca nombres de campos HTML.
    """
    datos = form.cleaned_data
    lineas: tuple[LineaFicha, ...] = lineas_desde_formset(formset)

    return DatosIngreso(
        patente=datos["patente"],
        cliente_nombre=datos["cliente_nombre"],
        cliente_telefono=datos["cliente_telefono"],
        cliente_email=datos["cliente_email"],
        marca=datos["marca"],
        modelo=datos["modelo"],
        anio=datos["anio"],
        color=datos["color"],
        fecha_ingreso=datos["fecha_ingreso"],
        kilometraje=datos["kilometraje"],
        observaciones=datos["observaciones"],
        proxima_mantencion_km=datos["proxima_mantencion_km"],
        proxima_mantencion_fecha=datos["proxima_mantencion_fecha"],
        lineas=lineas,
    )


# ---------------------------------------------------------------------------
# Corrección de una ficha guardada
# ---------------------------------------------------------------------------


def ficha_editar(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Corrige las líneas y las observaciones de una visita ya registrada.

    No permite cambiar el vehículo, el dueño, la fecha ni el kilometraje: esos
    datos identifican la visita en el historial del auto.
    """
    orden = get_object_or_404(orden_de_visita(pk))

    if request.method == "POST":
        form = FichaEdicionForm(request.POST)
        formset = LineaFichaFormSet(request.POST, prefix=PREFIJO_LINEAS)
        if form.is_valid() and formset.is_valid():
            return _actualizar_ficha(request, orden, form, formset)
    else:
        form = FichaEdicionForm.desde_orden(orden)
        formset = LineaFichaFormSet(initial=lineas_iniciales(orden), prefix=PREFIJO_LINEAS)

    return _render_edicion(request, orden, form, formset)


def _render_edicion(
    request: HttpRequest,
    orden,
    form: FichaEdicionForm,
    formset: LineaFichaFormSet,
) -> HttpResponse:
    contexto = {
        "orden": orden,
        "form": form,
        "formset": formset,
        "catalogo": TipoItemFicha.choices,
    }
    return render(request, "workshop/ficha_editar.html", contexto)


def _actualizar_ficha(
    request: HttpRequest,
    orden,
    form: FichaEdicionForm,
    formset: LineaFichaFormSet,
) -> HttpResponse:
    try:
        build_actualizar_ficha_service().actualizar(
            orden,
            lineas=lineas_desde_formset(formset),
            observaciones=form.cleaned_data["observaciones"],
        )
    except WorkshopDomainError as exc:
        logger.warning("Corrección rechazada por el dominio: %s", exc)
        form.add_error(None, str(exc))
        return _render_edicion(request, orden, form, formset)

    messages.success(request, f"Ficha actualizada para {orden.vehiculo.patente}.")
    return redirect("workshop:vehiculo", patente=orden.vehiculo.patente)


# ---------------------------------------------------------------------------
# Ficha imprimible
# ---------------------------------------------------------------------------


def ficha_imprimir(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Ficha lista para imprimir y entregar al cliente.

    Imprime solo lo que trae la ficha de papel: el encabezado del taller, la
    fecha, marca y patente, las líneas usadas, el total y las observaciones.
    """
    orden = get_object_or_404(orden_de_visita(pk))

    contexto = {
        "orden": orden,
        "lineas": orden.items.all(),
        "taller": datos_del_taller(),
    }
    return render(request, "workshop/ficha_imprimible.html", contexto)

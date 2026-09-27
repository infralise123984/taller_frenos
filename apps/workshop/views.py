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

from apps.workshop.exceptions import IngresoDuplicadoError, PatenteInvalidaError
from apps.workshop.forms import BuscarPatenteForm, IngresoRapidoForm
from apps.workshop.models import Cliente, Vehiculo
from apps.workshop.patentes import normalize_patente
from apps.workshop.selectors import (
    buscar_vehiculos,
    historial_de_cliente,
    historial_de_vehiculo,
    ingresos_recientes,
    resumen_de_vehiculo,
    vehiculos_de_cliente,
)
from apps.workshop.services import (
    DatosIngreso,
    TrabajoSolicitado,
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
    """Registra cliente, vehículo y visita en una sola pasada."""
    inicial = {}
    patente_precargada = (request.GET.get("patente") or "").strip().upper()
    if patente_precargada:
        inicial["patente"] = patente_precargada

    if request.method == "POST":
        form = IngresoRapidoForm(request.POST)
        if form.is_valid():
            return _registrar_ingreso(request, form)
    else:
        form = IngresoRapidoForm(initial=inicial)

    return render(request, "workshop/ingreso_form.html", {"form": form})


def _registrar_ingreso(request: HttpRequest, form: IngresoRapidoForm) -> HttpResponse:
    try:
        resultado = build_registro_ingreso_service().registrar(_datos_desde_formulario(form))
    except PatenteInvalidaError as exc:
        form.add_error("patente", str(exc))
        return render(request, "workshop/ingreso_form.html", {"form": form})
    except IngresoDuplicadoError:
        messages.warning(
            request,
            "Este vehículo ya tiene un ingreso con la misma fecha y kilometraje. "
            "Te mostramos el registro existente.",
        )
        return redirect("workshop:vehiculo", patente=form.cleaned_data["patente"])

    mensaje = (
        "Vehículo registrado correctamente."
        if resultado.vehiculo_creado
        else f"Nueva visita agregada para {resultado.vehiculo.patente}."
    )
    if resultado.cliente_creado:
        mensaje = f"{mensaje} Se creó la ficha del cliente."
    messages.success(request, mensaje)

    return redirect("workshop:vehiculo", patente=resultado.vehiculo.patente)


def _datos_desde_formulario(form: IngresoRapidoForm) -> DatosIngreso:
    """
    Traduce el formulario al contrato del servicio.

    Se mantiene aparte para que el dominio no conozca nombres de campos HTML.
    """
    datos = form.cleaned_data
    trabajos = tuple(TrabajoSolicitado(tipo=tipo) for tipo in datos["trabajos"])

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
        trabajos=trabajos,
    )

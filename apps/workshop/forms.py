"""Formularios de la gestión del taller."""

from __future__ import annotations

from datetime import date

from django import forms
from django.utils import timezone

from apps.ui import INPUT, INPUT_COMPACTO, TEXTAREA
from apps.workshop.models import TipoTrabajo
from apps.workshop.patentes import is_valid_patente, normalize_patente


class BuscarPatenteForm(forms.Form):
    """Buscador principal: la patente es el único dato que se pide."""

    patente = forms.CharField(
        label="Patente",
        max_length=8,
        widget=forms.TextInput(
            attrs={
                "class": (
                    "w-full rounded-2xl border-2 border-slate-300 bg-white px-5 py-5 "
                    "text-center text-3xl font-bold uppercase tracking-[0.25em] text-slate-900 "
                    "shadow-sm placeholder:text-slate-300 placeholder:tracking-normal "
                    "focus:border-sky-600 focus:outline-none focus:ring-4 focus:ring-sky-100"
                ),
                "placeholder": "ABCD12",
                "autocomplete": "off",
                "autocapitalize": "characters",
                "spellcheck": "false",
                "inputmode": "text",
                "autofocus": True,
            }
        ),
    )

    def clean_patente(self) -> str:
        patente = normalize_patente(self.cleaned_data["patente"])
        if not patente:
            raise forms.ValidationError("Escribe la patente del vehículo.")
        return patente


class IngresoRapidoForm(forms.Form):
    """
    Registro de un ingreso completo en una sola pantalla.

    Agrupa los datos del cliente, del vehículo y del trabajo realizado porque en
    el mesón se capturan de una sola vez, con el cliente esperando.
    """

    # -- Vehículo ---------------------------------------------------------
    patente = forms.CharField(
        label="Patente",
        max_length=8,
        widget=forms.TextInput(
            attrs={
                "class": f"{INPUT} font-bold uppercase tracking-widest",
                "placeholder": "ABCD12",
                "autocomplete": "off",
                "autocapitalize": "characters",
                "spellcheck": "false",
            }
        ),
    )
    marca = forms.CharField(
        label="Marca", max_length=60, required=False, widget=forms.TextInput(attrs={"class": INPUT})
    )
    modelo = forms.CharField(
        label="Modelo",
        max_length=60,
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT}),
    )
    anio = forms.IntegerField(
        label="Año", required=False, widget=forms.NumberInput(attrs={"class": INPUT})
    )
    color = forms.CharField(
        label="Color", max_length=40, required=False, widget=forms.TextInput(attrs={"class": INPUT})
    )

    # -- Cliente ----------------------------------------------------------
    cliente_nombre = forms.CharField(
        label="Nombre del cliente", max_length=150, widget=forms.TextInput(attrs={"class": INPUT})
    )
    cliente_telefono = forms.CharField(
        label="Teléfono / WhatsApp",
        max_length=32,
        widget=forms.TextInput(
            attrs={"class": INPUT, "inputmode": "tel", "placeholder": "+56 9 1234 5678"}
        ),
    )
    cliente_email = forms.EmailField(
        label="Correo (opcional)", required=False, widget=forms.EmailInput(attrs={"class": INPUT})
    )

    # -- Visita -----------------------------------------------------------
    fecha_ingreso = forms.DateField(
        label="Fecha de ingreso",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": INPUT, "type": "date"}),
    )
    kilometraje = forms.IntegerField(
        label="Kilometraje",
        min_value=0,
        widget=forms.NumberInput(
            attrs={"class": INPUT, "inputmode": "numeric", "placeholder": "120000"}
        ),
    )
    trabajos = forms.MultipleChoiceField(
        label="Trabajos realizados",
        choices=TipoTrabajo.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"class": TEXTAREA, "rows": 3}),
    )

    # -- Recomendación de próxima mantención -------------------------------
    proxima_mantencion_km = forms.IntegerField(
        label="Volver a los (km)",
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": INPUT_COMPACTO, "inputmode": "numeric"}),
    )
    proxima_mantencion_fecha = forms.DateField(
        label="O volver el",
        required=False,
        widget=forms.DateInput(attrs={"class": INPUT_COMPACTO, "type": "date"}),
    )

    # -- Validación --------------------------------------------------------

    def clean_patente(self) -> str:
        patente = normalize_patente(self.cleaned_data["patente"])
        if not is_valid_patente(patente):
            raise forms.ValidationError(
                "Revisa la patente: debe tener entre 4 y 8 caracteres, con letras y números."
            )
        return patente

    def clean_anio(self) -> int | None:
        anio = self.cleaned_data.get("anio")
        if anio is None:
            return None
        # Se admite hasta el año siguiente para no rechazar vehículos nuevos.
        limite = timezone.localdate().year + 1
        if not 1900 <= anio <= limite:
            raise forms.ValidationError(f"El año debe estar entre 1900 y {limite}.")
        return anio

    def clean(self):
        cleaned = super().clean()
        fecha_ingreso: date | None = cleaned.get("fecha_ingreso")
        proxima_fecha: date | None = cleaned.get("proxima_mantencion_fecha")

        if fecha_ingreso and proxima_fecha and proxima_fecha <= fecha_ingreso:
            self.add_error(
                "proxima_mantencion_fecha",
                "La próxima mantención debe ser posterior a la fecha de ingreso.",
            )
        return cleaned

    # -- Presentación ------------------------------------------------------

    def grouped_trabajos(self) -> list[dict[str, object]]:
        """Opciones del catálogo con su estado de selección, para dibujar los botones."""
        valor = self["trabajos"].value() or []
        seleccionados = {valor} if isinstance(valor, str) else set(valor)
        return [
            {
                "value": value,
                "label": label,
                "checked": value in seleccionados,
            }
            for value, label in TipoTrabajo.choices
        ]

"""Formularios de la gestión del taller."""

from __future__ import annotations

from datetime import date

from django import forms
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils import timezone
from django.utils.formats import number_format

from apps.ui import INPUT, INPUT_COMPACTO, SELECT, TEXTAREA
from apps.workshop.models import TOPE_PRECIO, TipoItemFicha
from apps.workshop.patentes import is_valid_patente, normalize_patente
from apps.workshop.services import LineaFicha

# Cada ficha es una visita real del mesón: más de 30 líneas es un error de
# digitación, no un trabajo de frenos.
MAX_LINEAS_FICHA = 30

# Prefijo del formset de líneas. Da nombre a los campos (``lineas-0-precio``),
# y lo comparten la vista, las plantillas y el JavaScript.
PREFIJO_LINEAS = "lineas"


def formato_pesos(monto: int) -> str:
    """Monto en pesos para mensajes de error, con el separador de miles local."""
    return f"${number_format(monto, decimal_pos=0, use_l10n=True, force_grouping=True)}"


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


# ---------------------------------------------------------------------------
# Líneas de la ficha
# ---------------------------------------------------------------------------


class LineaFichaForm(forms.Form):
    """
    Una línea de la ficha: el trabajo elegido del catálogo y su precio.

    El detalle es texto libre porque ahí la operadora anota la posición del
    trabajo ("trasero") y cualquier observación de la línea.
    """

    # No es ``required`` para que la línea en blanco no muestre un error
    # genérico: la elección del trabajo se exige en ``clean_tipo``, que explica
    # qué falta con las palabras del taller.
    tipo = forms.ChoiceField(
        label="Trabajo",
        choices=[("", "Elige un trabajo…"), *TipoItemFicha.choices],
        required=False,
        widget=forms.Select(attrs={"class": SELECT}),
    )
    detalle = forms.CharField(
        label="Detalle",
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": INPUT, "placeholder": "trasero, delantero…", "autocomplete": "off"}
        ),
    )
    codigo_repuesto = forms.CharField(
        label="Código",
        max_length=60,
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "off"}),
    )
    marca_repuesto = forms.CharField(
        label="Marca",
        max_length=60,
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "off"}),
    )
    precio = forms.IntegerField(
        label="Precio",
        required=False,
        min_value=-TOPE_PRECIO,
        max_value=TOPE_PRECIO,
        initial=0,
        widget=forms.NumberInput(
            attrs={"class": INPUT, "inputmode": "numeric", "step": "1", "placeholder": "0"}
        ),
    )

    def clean_tipo(self) -> str:
        tipo = self.cleaned_data["tipo"]
        if not tipo:
            raise forms.ValidationError("Elige el trabajo de esta línea.")
        return tipo

    def clean_precio(self) -> int:
        return self.cleaned_data.get("precio") or 0

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        precio = cleaned.get("precio") or 0

        # El descuento es la única línea que resta; el resto son montos positivos.
        if precio < 0 and tipo != TipoItemFicha.DESCUENTO:
            self.add_error(
                "precio",
                "Solo la línea de descuento puede llevar un monto negativo.",
            )
        return cleaned


class BaseLineaFichaFormSet(forms.BaseFormSet):
    """Reglas de la ficha completa: al menos una línea y un total que no sea negativo."""

    def add_fields(self, form, index):
        super().add_fields(form, index)

        # La casilla de borrado actúa por detrás del botón "Quitar línea", así
        # que no debe recibir el foco por teclado: nadie la ve.
        casilla = form.fields.get(DELETION_FIELD_NAME)
        if casilla is not None:
            casilla.widget.attrs.update({"class": "borrar-linea", "tabindex": "-1"})

    def clean(self):
        if any(self.errors):
            return

        lineas: list[LineaFichaForm] = [
            form for form in self.forms if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
        if not lineas:
            raise forms.ValidationError("Agrega al menos una línea a la ficha.")

        total = sum(form.cleaned_data.get("precio") or 0 for form in lineas)
        if total < 0:
            raise forms.ValidationError(
                "El descuento no puede dejar el total en negativo "
                f"(el total quedaría en {formato_pesos(total)})."
            )


LineaFichaFormSet = forms.formset_factory(
    LineaFichaForm,
    formset=BaseLineaFichaFormSet,
    extra=1,
    max_num=MAX_LINEAS_FICHA,
    validate_max=True,
    can_delete=True,
)

LineaFichaEdicionFormSet = forms.formset_factory(
    LineaFichaForm,
    formset=BaseLineaFichaFormSet,
    extra=0,
    max_num=MAX_LINEAS_FICHA,
    validate_max=True,
    can_delete=True,
)


# ---------------------------------------------------------------------------
# Corrección de una ficha guardada
# ---------------------------------------------------------------------------


class FichaEdicionForm(forms.Form):
    """
    Corrección de una visita: solo sus líneas y sus observaciones.

    El vehículo, el dueño, la fecha y el kilometraje no se editan aquí: un dato
    mal digitado de esas características se corrige registrando la visita de
    nuevo, para no alterar el historial.
    """

    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"class": TEXTAREA, "rows": 3}),
    )

    @classmethod
    def desde_orden(cls, orden) -> FichaEdicionForm:
        return cls(initial={"observaciones": orden.observaciones})


def lineas_iniciales(orden) -> list[dict[str, object]]:
    """Líneas guardadas de una visita, en el formato que espera el formset."""
    return [
        {
            "tipo": item.tipo,
            "detalle": item.detalle,
            "codigo_repuesto": item.codigo_repuesto,
            "marca_repuesto": item.marca_repuesto,
            "precio": item.precio,
        }
        for item in orden.items.all()
    ]


def lineas_desde_formset(formset) -> tuple[LineaFicha, ...]:
    """
    Traduce el formset al contrato del dominio.

    Se mantiene fuera de la vista para que el dominio no conozca nombres de
    campos HTML ni el formato del formset. No llegan al dominio las filas
    marcadas para quitar ni las que quedaron en blanco: Django entrega estas
    últimas sin datos que limpiar (``cleaned_data`` vacío), y la primera fila de
    sobra siempre viaja en el formulario.
    """
    lineas: list[LineaFicha] = []

    for datos in formset.cleaned_data:
        if datos.get("DELETE") or not datos.get("tipo"):
            continue

        lineas.append(
            LineaFicha(
                tipo=datos["tipo"],
                precio=datos.get("precio") or 0,
                detalle=datos.get("detalle", ""),
                codigo_repuesto=datos.get("codigo_repuesto", ""),
                marca_repuesto=datos.get("marca_repuesto", ""),
            )
        )

    return tuple(lineas)

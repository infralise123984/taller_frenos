"""Ayudas compartidas por las pruebas de la ficha de trabajo."""

from __future__ import annotations

from apps.workshop.forms import MAX_LINEAS_FICHA, PREFIJO_LINEAS
from apps.workshop.models import TipoItemFicha


def payload_lineas(*lineas: dict[str, object]) -> dict[str, str]:
    """
    Datos del formset de líneas, incluido su formulario de gestión.

    Cada línea es un diccionario con las claves ``tipo``, ``precio``,
    ``detalle``, ``codigo_repuesto``, ``marca_repuesto`` y ``DELETE``, todas
    opcionales: se arma una línea válida con una sola de ellas.
    """
    datos = {
        f"{PREFIJO_LINEAS}-TOTAL_FORMS": str(len(lineas)),
        f"{PREFIJO_LINEAS}-INITIAL_FORMS": "0",
        f"{PREFIJO_LINEAS}-MIN_NUM_FORMS": "0",
        f"{PREFIJO_LINEAS}-MAX_NUM_FORMS": str(MAX_LINEAS_FICHA),
    }

    for indice, linea in enumerate(lineas):
        datos[f"{PREFIJO_LINEAS}-{indice}-tipo"] = str(linea.get("tipo", TipoItemFicha.OBRA_MANO))
        datos[f"{PREFIJO_LINEAS}-{indice}-precio"] = str(linea.get("precio", 0))
        datos[f"{PREFIJO_LINEAS}-{indice}-detalle"] = str(linea.get("detalle", ""))
        datos[f"{PREFIJO_LINEAS}-{indice}-codigo_repuesto"] = str(linea.get("codigo_repuesto", ""))
        datos[f"{PREFIJO_LINEAS}-{indice}-marca_repuesto"] = str(linea.get("marca_repuesto", ""))
        if linea.get("DELETE"):
            datos[f"{PREFIJO_LINEAS}-{indice}-DELETE"] = "on"

    return datos

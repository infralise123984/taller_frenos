"""
Pruebas de la localización chilena.

Es una preocupación transversal del proyecto, pero Django descubre las pruebas
por app, así que se alojan aquí para que se ejecuten con el resto.

Protegen una configuración silenciosa: si el locale deja de resolverse, los
montos y las fechas vuelven al inglés sin que nada falle.
"""

from __future__ import annotations

from datetime import date

from django import forms
from django.test import SimpleTestCase
from django.utils import formats
from django.utils.translation import get_language, override


class FormatosChilenosTests(SimpleTestCase):
    def test_el_idioma_activo_es_el_chileno(self) -> None:
        self.assertEqual(get_language(), "es-cl")

    def test_separa_los_miles_con_punto(self) -> None:
        with override("es-cl"):
            self.assertEqual(formats.number_format(88_900, force_grouping=True), "88.900")
            self.assertEqual(formats.number_format(1_234_567, force_grouping=True), "1.234.567")

    def test_usa_coma_como_separador_decimal(self) -> None:
        with override("es-cl"):
            self.assertEqual(
                formats.number_format(1234.5, decimal_pos=1, force_grouping=True), "1.234,5"
            )

    def test_los_meses_se_escriben_en_español(self) -> None:
        with override("es-cl"):
            self.assertEqual(
                formats.date_format(date(2026, 7, 29), r"j \d\e F \d\e Y"),
                "29 de julio de 2026",
            )

    def test_los_campos_de_fecha_aceptan_el_formato_iso_del_navegador(self) -> None:
        """
        <input type="date"> envía siempre "AAAA-MM-DD": si el locale no declara
        ese formato de entrada, el formulario de ingreso rechazaría la fecha.
        """
        with override("es-cl"):
            self.assertEqual(forms.DateField().clean("2026-09-27"), date(2026, 9, 27))

    def test_los_campos_de_fecha_tambien_aceptan_el_formato_local(self) -> None:
        with override("es-cl"):
            self.assertEqual(forms.DateField().clean("27/09/2026"), date(2026, 9, 27))

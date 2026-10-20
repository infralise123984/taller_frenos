"""Pruebas del formset de líneas de la ficha."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.workshop.forms import (
    MAX_LINEAS_FICHA,
    PREFIJO_LINEAS,
    LineaFichaFormSet,
    lineas_desde_formset,
)
from apps.workshop.models import TOPE_PRECIO, TipoItemFicha
from apps.workshop.tests.helpers import payload_lineas


class LineaFichaFormSetTests(SimpleTestCase):
    """El formset es puro: no necesita base de datos."""

    def _formset(self, *lineas: dict[str, object], blancas: int = 0) -> LineaFichaFormSet:
        return LineaFichaFormSet(
            payload_lineas(*lineas, blancas=blancas),
            prefix=PREFIJO_LINEAS,
        )

    # -- Camino feliz -------------------------------------------------------
    def test_acepta_una_linea_con_su_precio_y_su_detalle(self) -> None:
        formset = self._formset(
            {
                "tipo": TipoItemFicha.PASTILLAS,
                "precio": 32_000,
                "detalle": "trasero",
                "codigo_repuesto": "23479",
                "marca_repuesto": "Bosch",
            }
        )

        self.assertTrue(formset.is_valid(), formset.errors)

        linea = formset.cleaned_data[0]
        self.assertEqual(linea["tipo"], TipoItemFicha.PASTILLAS)
        self.assertEqual(linea["precio"], 32_000)
        self.assertEqual(linea["detalle"], "trasero")
        self.assertEqual(linea["codigo_repuesto"], "23479")
        self.assertEqual(linea["marca_repuesto"], "Bosch")

    def test_discos_nuevos_aparece_debajo_de_rectificado_de_discos(self) -> None:
        opciones = list(TipoItemFicha.choices)
        indice_rectificado = next(
            indice
            for indice, (valor, _) in enumerate(opciones)
            if valor == TipoItemFicha.RECT_DISCO
        )

        self.assertEqual(
            opciones[indice_rectificado + 1],
            (TipoItemFicha.DISCOS_NUEVOS, TipoItemFicha.DISCOS_NUEVOS.label),
        )
        formset = self._formset({"tipo": TipoItemFicha.DISCOS_NUEVOS, "precio": 45_000})
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_cilindros_nuevos_aparece_debajo_de_rectificado_de_tambores(self) -> None:
        opciones = list(TipoItemFicha.choices)
        indice_rectificado = next(
            indice
            for indice, (valor, _) in enumerate(opciones)
            if valor == TipoItemFicha.RECT_TAMBORES
        )

        self.assertEqual(
            opciones[indice_rectificado + 1],
            (TipoItemFicha.CILINDROS_NUEVOS, TipoItemFicha.CILINDROS_NUEVOS.label),
        )
        formset = self._formset({"tipo": TipoItemFicha.CILINDROS_NUEVOS, "precio": 20_000})
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_acepta_varias_lineas_y_el_mismo_trabajo_repetido(self) -> None:
        formset = self._formset(
            {"tipo": TipoItemFicha.PASTILLAS, "precio": 32_000, "detalle": "delantero"},
            {"tipo": TipoItemFicha.PASTILLAS, "precio": 29_000, "detalle": "trasero"},
            {"tipo": TipoItemFicha.OBRA_MANO, "precio": 25_000},
        )

        self.assertTrue(formset.is_valid(), formset.errors)
        self.assertEqual(len(formset.cleaned_data), 3)

    def test_una_linea_sin_precio_queda_en_cero(self) -> None:
        formset = self._formset({"tipo": TipoItemFicha.FLEXIBLE})

        self.assertTrue(formset.is_valid(), formset.errors)
        self.assertEqual(formset.cleaned_data[0]["precio"], 0)

    def test_acepta_una_linea_de_descuento_con_monto_negativo(self) -> None:
        formset = self._formset(
            {"tipo": TipoItemFicha.OBRA_MANO, "precio": 25_000},
            {"tipo": TipoItemFicha.DESCUENTO, "precio": -5_000, "detalle": "cliente frecuente"},
        )

        self.assertTrue(formset.is_valid(), formset.errors)
        self.assertEqual(formset.cleaned_data[1]["precio"], -5_000)

    # -- Reglas de la ficha -------------------------------------------------

    def test_rechaza_una_ficha_sin_lineas(self) -> None:
        formset = self._formset()

        self.assertFalse(formset.is_valid())
        self.assertIn("Agrega al menos una línea", str(formset.non_form_errors()))

    def test_rechaza_una_ficha_cuyas_lineas_se_borraron_todas(self) -> None:
        formset = self._formset({"tipo": TipoItemFicha.PASTILLAS, "precio": 32_000, "DELETE": True})

        self.assertFalse(formset.is_valid())
        self.assertIn("Agrega al menos una línea", str(formset.non_form_errors()))

    def test_rechaza_un_monto_negativo_fuera_de_la_linea_de_descuento(self) -> None:
        formset = self._formset({"tipo": TipoItemFicha.PASTILLAS, "precio": -1_000})

        self.assertFalse(formset.is_valid())
        self.assertIn(
            "Solo la línea de descuento puede llevar un monto negativo",
            str(formset.errors),
        )

    def test_rechaza_un_descuento_mayor_que_el_total(self) -> None:
        formset = self._formset(
            {"tipo": TipoItemFicha.OBRA_MANO, "precio": 10_000},
            {"tipo": TipoItemFicha.DESCUENTO, "precio": -12_000},
        )

        self.assertFalse(formset.is_valid())
        self.assertIn("no puede dejar el total en negativo", str(formset.non_form_errors()))

    def test_rechaza_un_precio_mayor_que_el_tope(self) -> None:
        formset = self._formset(
            {"tipo": TipoItemFicha.OBRA_MANO, "precio": TOPE_PRECIO + 1},
        )

        self.assertFalse(formset.is_valid())
        self.assertIn("precio", formset.errors[0])

    def test_acepta_el_maximo_de_lineas_y_rechaza_una_mas(self) -> None:
        hasta_el_maximo = self._formset(
            *[{"tipo": TipoItemFicha.PATINES, "precio": 1_000}] * MAX_LINEAS_FICHA
        )
        self.assertTrue(hasta_el_maximo.is_valid(), hasta_el_maximo.errors)

        una_mas = self._formset(
            *[{"tipo": TipoItemFicha.PATINES, "precio": 1_000}] * (MAX_LINEAS_FICHA + 1)
        )
        self.assertFalse(una_mas.is_valid())

    def test_rechaza_una_linea_con_precio_pero_sin_trabajo_elegido(self) -> None:
        formset = self._formset({"tipo": "", "precio": 12_000})

        self.assertFalse(formset.is_valid())
        self.assertIn("Elige el trabajo de esta línea", str(formset.errors))

    def test_rechaza_un_trabajo_que_no_esta_en_el_catalogo(self) -> None:
        formset = self._formset({"tipo": "cambiar_el_aceite", "precio": 5_000})

        self.assertFalse(formset.is_valid())
        self.assertIn("tipo", formset.errors[0])

    # -- Filas de sobra -----------------------------------------------------

    def test_ignora_la_fila_en_blanco_que_sobra_en_el_formulario(self) -> None:
        """
        El navegador siempre manda una fila sin usar; Django la entrega con
        ``cleaned_data`` vacío y no debe convertirse en una línea.
        """
        formset = self._formset({"tipo": TipoItemFicha.PASTILLAS, "precio": 32_000}, blancas=1)

        self.assertTrue(formset.is_valid(), formset.errors)

        lineas = lineas_desde_formset(formset)
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0].tipo, TipoItemFicha.PASTILLAS)

    def test_una_ficha_con_solo_filas_en_blanco_se_rechaza(self) -> None:
        formset = self._formset(blancas=2)

        self.assertFalse(formset.is_valid())
        self.assertIn("Agrega al menos una línea", str(formset.non_form_errors()))

    def test_varias_filas_en_blanco_no_afectan_a_las_lineas_llenas(self) -> None:
        formset = self._formset(
            {"tipo": TipoItemFicha.OBRA_MANO, "precio": 25_000},
            {"tipo": TipoItemFicha.DESCUENTO, "precio": -5_000},
            blancas=3,
        )

        self.assertTrue(formset.is_valid(), formset.errors)

        lineas = lineas_desde_formset(formset)
        self.assertEqual(len(lineas), 2)
        self.assertEqual(sum(linea.precio for linea in lineas), 20_000)

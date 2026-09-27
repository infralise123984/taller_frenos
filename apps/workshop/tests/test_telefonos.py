"""Pruebas de la normalización de teléfonos."""

from django.test import SimpleTestCase

from apps.workshop.telefonos import format_telefono, normalize_telefono


class NormalizarTelefonoTests(SimpleTestCase):
    def test_agrega_el_codigo_de_pais_a_un_movil_nacional(self) -> None:
        self.assertEqual(normalize_telefono("912345678"), "56912345678")

    def test_normaliza_formatos_con_espacios_y_guiones(self) -> None:
        self.assertEqual(normalize_telefono("+56 9 1234 5678"), "56912345678")
        self.assertEqual(normalize_telefono("56-9-1234-5678"), "56912345678")

    def test_unifica_variantes_del_mismo_numero(self) -> None:
        variantes = ["+56 9 8123 4567", "981234567", "56981234567", "9 8123 4567"]

        self.assertEqual({normalize_telefono(v) for v in variantes}, {"56981234567"})

    def test_devuelve_cadena_vacia_sin_digitos(self) -> None:
        self.assertEqual(normalize_telefono(""), "")
        self.assertEqual(normalize_telefono("sin número"), "")


class FormatearTelefonoTests(SimpleTestCase):
    def test_presenta_un_movil_chileno_de_forma_legible(self) -> None:
        self.assertEqual(format_telefono("56981234567"), "+56 9 8123 4567")

    def test_devuelve_el_valor_original_si_no_reconoce_el_formato(self) -> None:
        self.assertEqual(format_telefono("22334455"), "22334455")

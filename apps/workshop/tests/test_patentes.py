"""Pruebas de la normalización de patentes."""

from django.test import SimpleTestCase

from apps.workshop.patentes import is_valid_patente, normalize_patente


class NormalizarPatenteTests(SimpleTestCase):
    def test_elimina_separadores_y_pasa_a_mayusculas(self) -> None:
        self.assertEqual(normalize_patente(" ab-12 34 "), "AB1234")
        self.assertEqual(normalize_patente("abcd·12"), "ABCD12")

    def test_conserva_una_patente_ya_normalizada(self) -> None:
        self.assertEqual(normalize_patente("BJDF45"), "BJDF45")

    def test_devuelve_cadena_vacia_si_no_hay_contenido(self) -> None:
        self.assertEqual(normalize_patente(""), "")
        self.assertEqual(normalize_patente("   "), "")
        self.assertEqual(normalize_patente("---"), "")


class ValidarPatenteTests(SimpleTestCase):
    def test_acepta_formatos_chilenos_habituales(self) -> None:
        self.assertTrue(is_valid_patente("BJDF45"))
        self.assertTrue(is_valid_patente("ab-12 34"))

    def test_rechaza_cadenas_demasiado_cortas_o_largas(self) -> None:
        self.assertFalse(is_valid_patente("AB1"))
        self.assertFalse(is_valid_patente("ABCDEFGHIJ12"))

    def test_rechaza_cadenas_sin_letras_o_sin_numeros(self) -> None:
        self.assertFalse(is_valid_patente("123456"))
        self.assertFalse(is_valid_patente("ABCDEF"))

    def test_rechaza_cadenas_vacias(self) -> None:
        self.assertFalse(is_valid_patente(""))

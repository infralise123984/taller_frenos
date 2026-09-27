"""Pruebas del proveedor de OTP local."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.exceptions import OtpDeliveryError
from apps.accounts.models import OtpChallenge
from apps.accounts.providers.local import LocalOtpProvider

AJUSTES = {
    "OTP_CODE_LENGTH": 6,
    "OTP_TTL_SECONDS": 300,
    "OTP_MAX_ATTEMPTS": 3,
}


class CapturadorDeCodigos:
    """Doble de prueba que reemplaza al envío de correo real."""

    def __init__(self, *, fallar: bool = False) -> None:
        self.fallar = fallar
        self.envios: list[dict[str, object]] = []

    def __call__(self, *, email: str, code: str, ttl_seconds: int) -> None:
        if self.fallar:
            raise RuntimeError("SMTP caído")
        self.envios.append({"email": email, "code": code, "ttl_seconds": ttl_seconds})

    @property
    def ultimo_codigo(self) -> str:
        return str(self.envios[-1]["code"])


@override_settings(**AJUSTES)
class LocalOtpProviderTests(TestCase):
    def setUp(self) -> None:
        self.capturador = CapturadorDeCodigos()
        self.provider = LocalOtpProvider(
            code_length=AJUSTES["OTP_CODE_LENGTH"],
            ttl_seconds=AJUSTES["OTP_TTL_SECONDS"],
            max_attempts=AJUSTES["OTP_MAX_ATTEMPTS"],
            sender=self.capturador,
        )

    def test_genera_un_codigo_numerico_de_la_longitud_configurada(self) -> None:
        self.provider.send_code(email="taller@ejemplo.cl")

        codigo = self.capturador.ultimo_codigo
        self.assertEqual(len(codigo), 6)
        self.assertTrue(codigo.isdigit())

    def test_no_persiste_el_codigo_en_texto_plano(self) -> None:
        self.provider.send_code(email="taller@ejemplo.cl")

        desafio = OtpChallenge.objects.get()
        self.assertNotIn(self.capturador.ultimo_codigo, desafio.code_hash)
        self.assertTrue(check_password(self.capturador.ultimo_codigo, desafio.code_hash))

    def test_normaliza_el_correo_a_minusculas(self) -> None:
        self.provider.send_code(email="  Taller@Ejemplo.CL ")

        self.assertEqual(self.capturador.envios[-1]["email"], "taller@ejemplo.cl")

    def test_acepta_el_codigo_correcto_una_sola_vez(self) -> None:
        self.provider.send_code(email="taller@ejemplo.cl")
        codigo = self.capturador.ultimo_codigo

        self.assertTrue(self.provider.verify_code(email="taller@ejemplo.cl", code=codigo))
        self.assertFalse(self.provider.verify_code(email="taller@ejemplo.cl", code=codigo))

    def test_rechaza_un_codigo_incorrecto(self) -> None:
        self.provider.send_code(email="taller@ejemplo.cl")

        self.assertFalse(self.provider.verify_code(email="taller@ejemplo.cl", code="000000"))

    def test_un_codigo_mal_formado_no_consume_intentos(self) -> None:
        self.provider.send_code(email="taller@ejemplo.cl")

        self.assertFalse(self.provider.verify_code(email="taller@ejemplo.cl", code="abc"))
        self.assertEqual(OtpChallenge.objects.get().attempts, 0)

    def test_bloquea_tras_agotar_los_intentos(self) -> None:
        self.provider.send_code(email="taller@ejemplo.cl")
        codigo_correcto = self.capturador.ultimo_codigo

        for _ in range(AJUSTES["OTP_MAX_ATTEMPTS"]):
            self.provider.verify_code(email="taller@ejemplo.cl", code="111111")

        # Incluso con el código correcto, el desafío ya no es utilizable.
        self.assertFalse(self.provider.verify_code(email="taller@ejemplo.cl", code=codigo_correcto))

    def test_rechaza_un_codigo_expirado(self) -> None:
        self.provider.send_code(email="taller@ejemplo.cl")
        codigo = self.capturador.ultimo_codigo

        OtpChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

        self.assertFalse(self.provider.verify_code(email="taller@ejemplo.cl", code=codigo))

    def test_emitir_un_codigo_nuevo_invalida_el_anterior(self) -> None:
        self.provider.send_code(email="taller@ejemplo.cl")
        primer_codigo = self.capturador.ultimo_codigo

        self.provider.send_code(email="taller@ejemplo.cl")
        segundo_codigo = self.capturador.ultimo_codigo

        self.assertNotEqual(primer_codigo, segundo_codigo)
        self.assertFalse(self.provider.verify_code(email="taller@ejemplo.cl", code=primer_codigo))
        self.assertTrue(self.provider.verify_code(email="taller@ejemplo.cl", code=segundo_codigo))

    def test_un_fallo_de_envio_se_traduce_en_error_de_dominio(self) -> None:
        provider = LocalOtpProvider(
            code_length=6,
            ttl_seconds=300,
            max_attempts=3,
            sender=CapturadorDeCodigos(fallar=True),
        )

        with self.assertRaises(OtpDeliveryError):
            provider.send_code(email="taller@ejemplo.cl")

    def test_no_valida_sin_desafio_previo(self) -> None:
        self.assertFalse(self.provider.verify_code(email="nadie@ejemplo.cl", code="123456"))

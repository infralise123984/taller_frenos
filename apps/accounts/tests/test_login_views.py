"""Pruebas de las vistas de acceso."""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.test_login_service import EMAIL, ProveedorOtpFalso

CLAVE = "clave-de-prueba-1234"
PATCH_PROVIDER = "apps.accounts.services.authentication.get_otp_provider"


class AccesoRequeridoTests(TestCase):
    """La política es de denegación por defecto en todo el sitio."""

    def test_la_pantalla_de_acceso_es_publica(self) -> None:
        respuesta = self.client.get(reverse("accounts:login"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Entrar con contraseña")

    def test_la_pantalla_de_codigo_es_publica(self) -> None:
        respuesta = self.client.get(reverse("accounts:login_otp"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Entrar con código")

    def test_el_taller_exige_sesion(self) -> None:
        respuesta = self.client.get(reverse("workshop:buscar"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("accounts:login"), respuesta["Location"])

    def test_la_ficha_de_vehiculo_exige_sesion(self) -> None:
        respuesta = self.client.get(reverse("workshop:vehiculo", args=["ABCD12"]))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("accounts:login"), respuesta["Location"])


class AccesoConContrasenaTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.user = User.objects.create_user(
            email=EMAIL, password=CLAVE, full_name="Encargada Taller"
        )
        self.url = reverse("accounts:login")

    def test_un_acceso_correcto_inicia_sesion_y_redirige(self) -> None:
        respuesta = self.client.post(self.url, {"email": EMAIL, "password": CLAVE})

        self.assertRedirects(respuesta, reverse("workshop:buscar"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_una_credencial_incorrecta_no_inicia_sesion(self) -> None:
        respuesta = self.client.post(self.url, {"email": EMAIL, "password": "incorrecta"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Correo o contraseña incorrectos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_ignora_un_destino_externo_en_el_parametro_next(self) -> None:
        respuesta = self.client.post(
            f"{self.url}?next=https://sitio-malicioso.example.com",
            {"email": EMAIL, "password": CLAVE},
        )

        self.assertRedirects(respuesta, reverse("workshop:buscar"))

    def test_respeta_un_destino_interno_valido(self) -> None:
        destino = reverse("workshop:ingreso_create")

        respuesta = self.client.post(self.url, {"email": EMAIL, "password": CLAVE, "next": destino})

        self.assertRedirects(respuesta, destino)

    def test_una_sesion_iniciada_no_vuelve_a_ver_el_formulario(self) -> None:
        self.client.force_login(self.user)

        respuesta = self.client.get(self.url)

        self.assertRedirects(respuesta, reverse("workshop:buscar"))


class AccesoConCodigoTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.provider = ProveedorOtpFalso()
        self.patcher = patch(PATCH_PROVIDER, return_value=self.provider)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

        self.user = User.objects.create_user(
            email=EMAIL, password=CLAVE, full_name="Encargada Taller"
        )
        self.url = reverse("accounts:login_otp")

    def test_el_primer_paso_muestra_el_formulario_de_correo(self) -> None:
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Enviar código")

    def test_el_primer_paso_solicita_el_codigo_y_pide_ingresarlo(self) -> None:
        respuesta = self.client.post(self.url, {"action": "request", "email": EMAIL})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ingresa el código")
        self.assertEqual(self.provider.enviados, [(EMAIL, "127.0.0.1")])

    def test_un_codigo_valido_inicia_sesion(self) -> None:
        self.provider.codigos[EMAIL] = "123456"

        respuesta = self.client.post(
            self.url, {"action": "verify", "email": EMAIL, "code": "123456"}
        )

        self.assertRedirects(respuesta, reverse("workshop:buscar"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_un_codigo_incorrecto_no_inicia_sesion(self) -> None:
        self.provider.codigos[EMAIL] = "123456"

        respuesta = self.client.post(
            self.url, {"action": "verify", "email": EMAIL, "code": "000000"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "El código no es válido")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_un_codigo_con_letras_se_rechaza_en_el_formulario(self) -> None:
        respuesta = self.client.post(
            self.url, {"action": "verify", "email": EMAIL, "code": "abcdef"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "El código debe contener solo números")

    def test_no_revela_si_el_correo_esta_registrado(self) -> None:
        respuesta = self.client.post(
            self.url, {"action": "request", "email": "desconocido@taller.cl"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ingresa el código")

    def test_un_paso_desconocido_vuelve_al_inicio_del_flujo(self) -> None:
        respuesta = self.client.post(self.url, {"action": "cualquier-cosa"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Enviar código")


class CierreDeSesionTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email=EMAIL, password=CLAVE)
        self.client.force_login(self.user)
        self.url = reverse("accounts:logout")

    def test_el_cierre_requiere_post(self) -> None:
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 405)

    def test_el_post_cierra_la_sesion(self) -> None:
        respuesta = self.client.post(self.url)

        self.assertRedirects(respuesta, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

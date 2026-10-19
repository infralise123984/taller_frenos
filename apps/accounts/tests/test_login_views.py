"""Pruebas de las vistas de acceso."""

from __future__ import annotations

import re

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.test_login_service import EMAIL

CLAVE = "clave-de-prueba-1234"


class AccesoRequeridoTests(TestCase):
    """La política es de denegación por defecto en todo el sitio."""

    def test_la_pantalla_de_acceso_es_publica(self) -> None:
        respuesta = self.client.get(reverse("accounts:login"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Entrar con contraseña")
        self.assertNotContains(respuesta, "Código por correo")
        self.assertNotContains(respuesta, "avisa a la persona encargada")

    def test_el_acceso_con_codigo_ya_no_existe(self) -> None:
        respuesta = self.client.get("/cuenta/ingresar/codigo/")

        self.assertEqual(respuesta.status_code, 404)

    def test_un_post_al_antiguo_acceso_con_codigo_no_inicia_sesion(self) -> None:
        respuesta = self.client.post(
            "/cuenta/ingresar/codigo/",
            {"action": "verify", "email": EMAIL, "code": "123456"},
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertNotIn("_auth_user_id", self.client.session)

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


class ErroresDelIngresoTests(TestCase):
    """Los errores de campo deben quedar asociados al campo que los produjo."""

    def setUp(self) -> None:
        cache.clear()
        self.url = reverse("accounts:login")

    def test_los_errores_de_campo_apuntan_a_un_id_que_existe(self) -> None:
        respuesta = self.client.post(self.url, {"email": "", "password": ""})
        html = respuesta.content.decode()

        referenciados = re.findall(r'aria-describedby="([^"]+)"', html)
        disponibles = set(re.findall(r'id="([^"]+)"', html))

        self.assertTrue(referenciados, "el formulario debería describir sus errores")
        for referencia in referenciados:
            for destino in referencia.split():
                self.assertIn(destino, disponibles)

    def test_los_errores_de_campo_se_muestran_junto_al_campo(self) -> None:
        respuesta = self.client.post(self.url, {"email": "", "password": ""})

        self.assertContains(respuesta, "Este campo es obligatorio.")
        self.assertContains(respuesta, 'id="id_email_error"')


@override_settings(LOGIN_MAX_FAILED_ATTEMPTS=1, LOGIN_LOCKOUT_SECONDS=900)
class BloqueoDelIngresoTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.user = User.objects.create_user(email=EMAIL, password=CLAVE)
        self.url = reverse("accounts:login")

    def test_el_bloqueo_indica_la_hora_en_que_se_puede_volver(self) -> None:
        self.client.post(self.url, {"email": EMAIL, "password": "incorrecta"})
        respuesta = self.client.post(self.url, {"email": EMAIL, "password": "incorrecta"})

        self.assertContains(respuesta, "Bloqueamos el acceso por demasiados intentos fallidos")
        self.assertRegex(
            respuesta.content.decode(),
            r"Podrás intentarlo de nuevo a las \d{2}:\d{2}",
        )
        self.assertNotContains(respuesta, "minuto(s)")


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

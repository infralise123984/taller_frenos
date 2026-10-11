"""Pruebas del flujo de invitaciones."""

from __future__ import annotations

import re
from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.exceptions import CorreoYaRegistradoError, InvitacionInvalidaError
from apps.accounts.models import Invitacion, User
from apps.accounts.services import InvitacionService

CLAVE = "clave-de-prueba-1234"
NUEVA_CLAVE = "otra-clave-larga-2026"
INVITADO = "mecanico@taller.cl"
STAFF = "encargada@taller.cl"


class CapturadorDeEnvios:
    """Doble de prueba en lugar del envío real de correo."""

    def __init__(self, *, fallar: bool = False) -> None:
        self.fallar = fallar
        self.envios: list[dict[str, object]] = []

    def __call__(self, *, email, enlace, invitado_por, ttl_dias) -> None:
        if self.fallar:
            raise RuntimeError("SMTP caído")
        self.envios.append(
            {"email": email, "enlace": enlace, "invitado_por": invitado_por, "ttl_dias": ttl_dias}
        )


ENLACE_RE = re.compile(r"/cuenta/invitaciones/[^\s]+")


def ruta_de(cuerpo: str) -> str:
    """Extrae la ruta del enlace de aceptación desde el cuerpo del correo."""
    coincidencia = ENLACE_RE.search(cuerpo)
    if coincidencia is None:
        raise AssertionError(f"No hay enlace de invitación en: {cuerpo!r}")
    return coincidencia.group(0)


class InvitacionServiceTests(TestCase):
    def setUp(self) -> None:
        self.capturador = CapturadorDeEnvios()
        self.service = InvitacionService(sender=self.capturador)
        self.staff = User.objects.create_user(
            email=STAFF, password=CLAVE, full_name="Encargada", is_staff=True
        )

    def invitar(self, **overrides) -> Invitacion:
        datos = {"email": INVITADO, "invitado_por": self.staff, "base_url": "https://taller.cl/"}
        return self.service.invitar(**{**datos, **overrides}).invitacion

    # -- Emisión -----------------------------------------------------------

    def test_emite_una_invitacion_y_entrega_el_enlace(self) -> None:
        emitida = self.service.invitar(
            email=INVITADO, invitado_por=self.staff, base_url="https://taller.cl/"
        )

        self.assertEqual(emitida.invitacion.email, INVITADO)
        self.assertTrue(emitida.invitacion.is_usable)
        self.assertTrue(emitida.email_enviado)
        self.assertTrue(emitida.enlace.startswith("https://taller.cl/cuenta/invitaciones/"))
        self.assertEqual(self.capturador.envios[0]["email"], INVITADO)

    def test_no_guarda_el_token_en_claro(self) -> None:
        emitida = self.service.invitar(
            email=INVITADO, invitado_por=self.staff, base_url="https://taller.cl/"
        )

        token = emitida.enlace.rstrip("/").rsplit("/", 1)[-1]
        self.assertNotIn(token, emitida.invitacion.token_hash)
        self.assertEqual(len(emitida.invitacion.token_hash), 64)

    def test_normaliza_el_correo_a_minusculas(self) -> None:
        invitacion = self.invitar(email="  Mecanico@Taller.CL ")

        self.assertEqual(invitacion.email, "mecanico@taller.cl")

    def test_rechaza_un_correo_que_ya_tiene_cuenta(self) -> None:
        with self.assertRaises(CorreoYaRegistradoError):
            self.invitar(email=STAFF)

        self.assertFalse(Invitacion.objects.exists())

    def test_una_invitacion_nueva_anula_la_anterior_del_mismo_correo(self) -> None:
        primera = self.invitar()
        token_antiguo = self.capturador.envios[-1]["enlace"]

        segunda = self.invitar()

        primera.refresh_from_db()
        self.assertIsNotNone(primera.revoked_at)
        self.assertTrue(segunda.is_usable)

        with self.assertRaises(InvitacionInvalidaError):
            self.service.obtener_utilizable(token_antiguo.rstrip("/").rsplit("/", 1)[-1])

    def test_un_fallo_de_envio_no_invalida_la_invitacion(self) -> None:
        servicio = InvitacionService(sender=CapturadorDeEnvios(fallar=True))

        emitida = servicio.invitar(
            email=INVITADO, invitado_por=self.staff, base_url="https://taller.cl/"
        )

        self.assertFalse(emitida.email_enviado)
        self.assertTrue(emitida.invitacion.is_usable)
        self.assertTrue(emitida.enlace)

    def test_la_vigencia_configurada_se_aplica(self) -> None:
        servicio = InvitacionService(sender=self.capturador, ttl_dias=2)

        emitida = servicio.invitar(
            email=INVITADO, invitado_por=self.staff, base_url="https://taller.cl/"
        )

        margen = emitida.invitacion.expires_at - timezone.now()
        self.assertGreater(margen, timedelta(days=1, hours=23))
        self.assertLess(margen, timedelta(days=2, minutes=1))

    # -- Consulta ----------------------------------------------------------

    def test_el_token_emitido_permite_recuperar_la_invitacion(self) -> None:
        emitida = self.service.invitar(
            email=INVITADO, invitado_por=self.staff, base_url="https://taller.cl/"
        )

        token = emitida.enlace.rstrip("/").rsplit("/", 1)[-1]

        self.assertEqual(self.service.obtener_utilizable(token).pk, emitida.invitacion.pk)

    def test_un_token_desconocido_no_es_utilizable(self) -> None:
        with self.assertRaises(InvitacionInvalidaError):
            self.service.obtener_utilizable("token-inventado")

    def test_una_invitacion_expirada_no_es_utilizable(self) -> None:
        invitacion = self.invitar()
        token = self.capturador.envios[-1]["enlace"].rstrip("/").rsplit("/", 1)[-1]

        Invitacion.objects.filter(pk=invitacion.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        with self.assertRaises(InvitacionInvalidaError):
            self.service.obtener_utilizable(token)

    # -- Consumo -----------------------------------------------------------

    def test_aceptar_crea_la_cuenta_y_consume_la_invitacion(self) -> None:
        emitida = self.service.invitar(
            email=INVITADO, invitado_por=self.staff, base_url="https://taller.cl/"
        )
        token = emitida.enlace.rstrip("/").rsplit("/", 1)[-1]

        usuario = self.service.aceptar(token=token, password=NUEVA_CLAVE)

        self.assertEqual(usuario.email, INVITADO)
        self.assertTrue(usuario.is_active)
        self.assertFalse(usuario.is_staff)
        self.assertTrue(usuario.check_password(NUEVA_CLAVE))

        emitida.invitacion.refresh_from_db()
        self.assertIsNotNone(emitida.invitacion.accepted_at)

    def test_el_mismo_enlace_no_sirve_dos_veces(self) -> None:
        emitida = self.service.invitar(
            email=INVITADO, invitado_por=self.staff, base_url="https://taller.cl/"
        )
        token = emitida.enlace.rstrip("/").rsplit("/", 1)[-1]
        self.service.aceptar(token=token, password=NUEVA_CLAVE)

        with self.assertRaises(InvitacionInvalidaError):
            self.service.aceptar(token=token, password=NUEVA_CLAVE)

        self.assertEqual(User.objects.filter(email=INVITADO).count(), 1)

    def test_aceptar_falla_si_la_cuenta_aparecio_entretanto(self) -> None:
        emitida = self.service.invitar(
            email=INVITADO, invitado_por=self.staff, base_url="https://taller.cl/"
        )
        token = emitida.enlace.rstrip("/").rsplit("/", 1)[-1]

        User.objects.create_user(email=INVITADO, password=CLAVE)

        with self.assertRaises(CorreoYaRegistradoError):
            self.service.aceptar(token=token, password=NUEVA_CLAVE)


class InvitacionesVistasTests(TestCase):
    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            email=STAFF, password=CLAVE, full_name="Encargada", is_staff=True
        )
        self.normal = User.objects.create_user(email="mecanico2@taller.cl", password=CLAVE)
        self.url = reverse("accounts:invitaciones")

    # -- Permisos ----------------------------------------------------------

    def test_exige_sesion_iniciada(self) -> None:
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("accounts:login"), respuesta["Location"])

    def test_una_cuenta_normal_no_puede_invitar(self) -> None:
        self.client.force_login(self.normal)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 403)

    def test_una_cuenta_normal_no_puede_invitar_por_post(self) -> None:
        self.client.force_login(self.normal)

        respuesta = self.client.post(self.url, {"email": INVITADO})

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Invitacion.objects.exists())

    # -- Emisión desde la pantalla -----------------------------------------

    def test_el_personal_con_acceso_al_panel_ve_la_pantalla(self) -> None:
        self.client.force_login(self.staff)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Invitar a una persona")

    def test_al_invitar_se_muestra_el_enlace_una_sola_vez(self) -> None:
        self.client.force_login(self.staff)

        respuesta = self.client.post(self.url, {"email": INVITADO}, follow=True)

        self.assertContains(respuesta, "Invitación lista")
        self.assertContains(respuesta, "/cuenta/invitaciones/")
        self.assertTrue(Invitacion.objects.filter(email=INVITADO).exists())

    def test_se_envia_el_correo_de_invitacion(self) -> None:
        self.client.force_login(self.staff)

        self.client.post(self.url, {"email": INVITADO})

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(INVITADO, mail.outbox[0].to)
        self.assertIn("/cuenta/invitaciones/", mail.outbox[0].body)

    def test_un_correo_ya_registrado_se_avisa_en_el_formulario(self) -> None:
        self.client.force_login(self.staff)

        respuesta = self.client.post(self.url, {"email": STAFF})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "ya tiene una cuenta")
        self.assertFalse(Invitacion.objects.exists())

    def test_un_correo_mal_escrito_se_rechaza(self) -> None:
        self.client.force_login(self.staff)

        respuesta = self.client.post(self.url, {"email": "no-es-un-correo"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Invitacion.objects.exists())

    # -- Aceptación --------------------------------------------------------

    def _crear_invitacion(self) -> str:
        self.client.force_login(self.staff)
        self.client.post(self.url, {"email": INVITADO})
        self.client.logout()
        return ruta_de(mail.outbox[-1].body)

    def test_la_pantalla_de_aceptacion_es_publica(self) -> None:
        ruta = self._crear_invitacion()

        respuesta = self.client.get(ruta)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Crea tu cuenta")
        self.assertContains(respuesta, INVITADO)
        self.assertContains(respuesta, "contacta a la persona administradora")
        self.assertNotContains(respuesta, "código por correo")

    def test_aceptar_crea_la_cuenta_e_inicia_sesion(self) -> None:
        ruta = self._crear_invitacion()

        respuesta = self.client.post(
            ruta, {"new_password1": NUEVA_CLAVE, "new_password2": NUEVA_CLAVE}
        )

        self.assertRedirects(respuesta, reverse("workshop:buscar"))
        usuario = User.objects.get(email=INVITADO)
        self.assertTrue(usuario.check_password(NUEVA_CLAVE))
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_una_contrasena_corta_se_rechaza(self) -> None:
        ruta = self._crear_invitacion()

        respuesta = self.client.post(ruta, {"new_password1": "corta", "new_password2": "corta"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(User.objects.filter(email=INVITADO).exists())

    def test_la_contrasena_se_repite_obligatoriamente(self) -> None:
        ruta = self._crear_invitacion()

        respuesta = self.client.post(
            ruta, {"new_password1": NUEVA_CLAVE, "new_password2": "otra-distinta-larga"}
        )

        self.assertContains(respuesta, "Las dos contraseñas no coinciden")
        self.assertFalse(User.objects.filter(email=INVITADO).exists())

    def test_un_token_inventado_no_permite_crear_cuenta(self) -> None:
        ruta = reverse("accounts:invitacion_aceptar", args=["token-inventado"])

        respuesta = self.client.get(ruta)

        self.assertEqual(respuesta.status_code, 410)
        self.assertContains(respuesta, "ya no sirve", status_code=410)

    def test_la_pantalla_de_enlace_vencido_no_muestra_marcadores_de_plantilla(self) -> None:
        """Un ``{#`` sin cerrar en la misma línea se imprime como texto."""
        ruta = reverse("accounts:invitacion_aceptar", args=["token-inventado"])

        html = self.client.get(ruta).content.decode()

        self.assertEqual([m for m in ("{#", "{%", "{{") if m in html], [])

    def test_un_enlace_ya_usado_no_permite_crear_otra_cuenta(self) -> None:
        ruta = self._crear_invitacion()
        self.client.post(ruta, {"new_password1": NUEVA_CLAVE, "new_password2": NUEVA_CLAVE})
        self.client.logout()

        respuesta = self.client.get(ruta)

        self.assertEqual(respuesta.status_code, 410)

    def test_una_sesion_abierta_no_ve_la_pantalla_de_aceptacion(self) -> None:
        ruta = self._crear_invitacion()
        self.client.force_login(self.normal)

        respuesta = self.client.get(ruta)

        self.assertRedirects(respuesta, reverse("workshop:buscar"))

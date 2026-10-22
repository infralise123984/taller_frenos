"""Pruebas de la pantalla para editar los datos del taller."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.workshop.models import (
    Cliente,
    DatosTaller,
    ItemTrabajo,
    OrdenTrabajo,
    TipoItemFicha,
    Vehiculo,
)

EMAIL = "recepcion@taller.cl"
CLAVE = "clave-de-prueba-1234"
DIRECCION = "Alameda N° 0779 al llegar a Av. Victoria"
CIUDAD = "Rancagua"
TELEFONO = "225 384 512"


class BaseDatosTallerTests(TestCase):
    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            email=EMAIL, password=CLAVE, full_name="Encargada", is_staff=True
        )
        self.normal = User.objects.create_user(
            email="mecanico@taller.cl", password=CLAVE, full_name="Mecánico"
        )
        self.url = reverse("workshop:datos_taller")
        self.client.force_login(self.staff)

    def payload(self, **overrides) -> dict[str, str]:
        datos = {"direccion": DIRECCION, "ciudad": CIUDAD, "telefono": TELEFONO}
        return {**datos, **overrides}

    def crear_orden(self) -> OrdenTrabajo:
        cliente = Cliente.objects.create(nombre="María Rojas", telefono="+56 9 8123 4567")
        vehiculo = Vehiculo.objects.create(patente="BJDF45", cliente=cliente, marca="Toyota")
        orden = OrdenTrabajo.objects.create(
            vehiculo=vehiculo,
            fecha_ingreso=timezone.localdate() - timedelta(days=30),
        )
        ItemTrabajo.objects.create(orden=orden, tipo=TipoItemFicha.OBRA_MANO, precio=25_000)
        return orden


class PermisosDatosTallerTests(BaseDatosTallerTests):
    def test_exige_sesion_iniciada(self) -> None:
        self.client.logout()

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("accounts:login"), respuesta["Location"])

    def test_una_cuenta_normal_no_puede_ver_la_pantalla(self) -> None:
        self.client.force_login(self.normal)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 403)

    def test_una_cuenta_normal_no_puede_guardar(self) -> None:
        self.client.force_login(self.normal)

        respuesta = self.client.post(self.url, self.payload())

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(DatosTaller.objects.exists())

    def test_el_enlace_solo_aparece_para_el_personal(self) -> None:
        respuesta = self.client.get(reverse("workshop:buscar"))
        self.assertContains(respuesta, self.url)

        self.client.force_login(self.normal)
        respuesta = self.client.get(reverse("workshop:buscar"))
        self.assertNotContains(respuesta, self.url)


class PantallaDatosTallerTests(BaseDatosTallerTests):
    def test_muestra_los_datos_guardados(self) -> None:
        DatosTaller.objects.create(direccion=DIRECCION, ciudad=CIUDAD, telefono=TELEFONO)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, DIRECCION)
        self.assertContains(respuesta, CIUDAD)
        self.assertContains(respuesta, TELEFONO)

    def test_avisa_cuando_todavia_no_hay_datos(self) -> None:
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, "sin dirección ni teléfono")

    def test_guardar_crea_la_fila_unica(self) -> None:
        respuesta = self.client.post(self.url, self.payload())

        self.assertRedirects(respuesta, self.url)
        taller = DatosTaller.get_solo()
        self.assertEqual(taller.pk, 1)
        self.assertEqual(taller.direccion, DIRECCION)
        self.assertEqual(taller.ciudad, CIUDAD)
        self.assertEqual(taller.telefono, TELEFONO)

    def test_guardar_dos_veces_actualiza_la_misma_fila(self) -> None:
        self.client.post(self.url, self.payload())
        self.client.post(self.url, self.payload(telefono="2 222 3333"))

        self.assertEqual(DatosTaller.objects.count(), 1)
        self.assertEqual(DatosTaller.get_solo().telefono, "2 222 3333")

    def test_recorta_los_espacios_sobrantes(self) -> None:
        self.client.post(
            self.url,
            self.payload(
                direccion="  Alameda 0779  ", ciudad=" Rancagua ", telefono=" 225 384 512 "
            ),
        )

        taller = DatosTaller.get_solo()
        self.assertEqual(taller.direccion, "Alameda 0779")
        self.assertEqual(taller.ciudad, "Rancagua")
        self.assertEqual(taller.telefono, "225 384 512")

    def test_rechaza_una_direccion_demasiado_larga(self) -> None:
        respuesta = self.client.post(self.url, self.payload(direccion="x" * 201))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(DatosTaller.objects.exists())

    def test_la_ficha_impresa_usa_los_datos_recien_guardados(self) -> None:
        orden = self.crear_orden()

        self.client.post(self.url, self.payload())
        respuesta = self.client.get(reverse("workshop:ficha_imprimir", args=[orden.pk]))

        self.assertContains(respuesta, DIRECCION)
        self.assertContains(respuesta, TELEFONO)

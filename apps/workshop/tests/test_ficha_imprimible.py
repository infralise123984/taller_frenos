"""Pruebas de la ficha imprimible y de los datos del taller."""

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


class BaseFichaImprimibleTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email=EMAIL, password=CLAVE, full_name="Encargada")
        self.client.force_login(self.user)

        self.cliente = Cliente.objects.create(nombre="María Rojas", telefono="+56 9 8123 4567")
        self.vehiculo = Vehiculo.objects.create(
            patente="BJDF45", cliente=self.cliente, marca="Toyota", modelo="Yaris"
        )
        self.orden = OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo,
            fecha_ingreso=timezone.localdate() - timedelta(days=30),
            kilometraje=78_400,
            observaciones="Chirrido al frenar.",
            proxima_mantencion_km=90_000,
        )
        ItemTrabajo.objects.create(
            orden=self.orden,
            tipo=TipoItemFicha.PASTILLAS,
            precio=32_000,
            detalle="trasero",
            codigo_repuesto="23479",
            marca_repuesto="Bosch",
        )
        ItemTrabajo.objects.create(orden=self.orden, tipo=TipoItemFicha.OBRA_MANO, precio=25_000)

    def _url(self) -> str:
        return reverse("workshop:ficha_imprimir", args=[self.orden.pk])


class FichaImprimibleTests(BaseFichaImprimibleTests):
    def test_muestra_las_lineas_usadas_con_su_precio_y_el_total(self) -> None:
        respuesta = self.client.get(self._url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "BJDF45")
        self.assertContains(respuesta, "Pastillas")
        self.assertContains(respuesta, "trasero")
        self.assertContains(respuesta, "23479")
        self.assertContains(respuesta, "32.000")
        self.assertContains(respuesta, "Obra de Mano")
        self.assertContains(respuesta, "57.000")

    def test_las_lineas_no_usadas_no_aparecen(self) -> None:
        respuesta = self.client.get(self._url())

        self.assertNotContains(respuesta, "Kit Bomba")
        self.assertNotContains(respuesta, "Rect. Tambores")

    def test_no_imprime_el_kilometraje_ni_la_proxima_mantencion(self) -> None:
        """El papel del taller no trae esos datos: la copia del cliente tampoco."""
        respuesta = self.client.get(self._url())

        self.assertNotContains(respuesta, "78.400")
        self.assertNotContains(respuesta, "90.000")
        self.assertNotContains(respuesta, "Próxima mantención")

    def test_imprime_las_observaciones(self) -> None:
        respuesta = self.client.get(self._url())

        self.assertContains(respuesta, "Chirrido al frenar.")

    def test_sin_sesion_iniciada_exige_ingresar(self) -> None:
        self.client.logout()

        respuesta = self.client.get(self._url())

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("accounts:login"), respuesta.url)

    def test_una_visita_inexistente_devuelve_404(self) -> None:
        respuesta = self.client.get(reverse("workshop:ficha_imprimir", args=[999_999]))

        self.assertEqual(respuesta.status_code, 404)


class EncabezadoDelTallerTests(BaseFichaImprimibleTests):
    def test_imprime_la_direccion_la_ciudad_y_el_telefono(self) -> None:
        DatosTaller.objects.create(direccion=DIRECCION, ciudad=CIUDAD, telefono=TELEFONO)

        respuesta = self.client.get(self._url())

        self.assertContains(respuesta, DIRECCION)
        self.assertContains(respuesta, CIUDAD)
        self.assertContains(respuesta, TELEFONO)

    def test_sin_datos_configurados_la_ficha_se_imprime_igual(self) -> None:
        respuesta = self.client.get(self._url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "TALLER V.M.D.")

    def test_omite_el_telefono_cuando_no_esta_cargado(self) -> None:
        DatosTaller.objects.create(direccion=DIRECCION, ciudad=CIUDAD)

        respuesta = self.client.get(self._url())

        self.assertNotContains(respuesta, "Fono:")


class DatosTallerTests(TestCase):
    def test_guardar_dos_veces_deja_una_sola_fila(self) -> None:
        DatosTaller.objects.create(direccion=DIRECCION, ciudad=CIUDAD, telefono=TELEFONO)

        ajuste = DatosTaller.get_solo()
        ajuste.direccion = "Otra dirección"
        ajuste.save()

        self.assertEqual(DatosTaller.objects.count(), 1)
        self.assertEqual(DatosTaller.get_solo().pk, 1)
        self.assertEqual(DatosTaller.get_solo().direccion, "Otra dirección")

    def test_sin_fila_configurada_devuelve_una_instancia_vacia(self) -> None:
        taller = DatosTaller.get_solo()

        self.assertEqual(taller.pk, None)
        self.assertEqual(taller.direccion, "")
        self.assertEqual(taller.telefono, "")

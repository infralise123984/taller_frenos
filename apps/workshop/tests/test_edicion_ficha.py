"""Pruebas de la corrección de una ficha ya guardada."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.workshop.models import Cliente, ItemTrabajo, OrdenTrabajo, TipoItemFicha, Vehiculo
from apps.workshop.tests.helpers import payload_lineas

EMAIL = "recepcion@taller.cl"
CLAVE = "clave-de-prueba-1234"


class EdicionFichaTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email=EMAIL, password=CLAVE, full_name="Encargada")
        self.client.force_login(self.user)

        self.cliente = Cliente.objects.create(nombre="María Rojas", telefono="+56 9 8123 4567")
        self.vehiculo = Vehiculo.objects.create(
            patente="BJDF45", cliente=self.cliente, marca="Toyota", modelo="Yaris"
        )
        self.fecha = timezone.localdate() - timedelta(days=30)
        self.orden = OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo,
            fecha_ingreso=self.fecha,
            kilometraje=78_400,
            observaciones="Chirrido al frenar.",
        )
        ItemTrabajo.objects.create(
            orden=self.orden,
            tipo=TipoItemFicha.PASTILLAS,
            precio=32_000,
            detalle="delantero",
        )

    def _url(self) -> str:
        return reverse("workshop:ficha_editar", args=[self.orden.pk])

    def _payload(self, *lineas: dict[str, object], **overrides) -> dict[str, object]:
        datos: dict[str, object] = {
            "observaciones": "Chirrido al frenar.",
            **payload_lineas(*lineas),
        }
        return {**datos, **overrides}

    def _lineas_guardadas(self) -> list[ItemTrabajo]:
        return list(self.orden.items.order_by("id"))

    # -- Corrección de las líneas ------------------------------------------

    def test_cambia_el_precio_de_una_linea(self) -> None:
        respuesta = self.client.post(
            self._url(),
            self._payload(
                {"tipo": TipoItemFicha.PASTILLAS, "precio": 40_000, "detalle": "delantero"}
            ),
        )

        self.assertRedirects(respuesta, reverse("workshop:vehiculo", args=["BJDF45"]))
        lineas = self._lineas_guardadas()
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0].precio, 40_000)
        self.assertEqual(self.orden.total, 40_000)

    def test_agrega_una_linea_nueva(self) -> None:
        self.client.post(
            self._url(),
            self._payload(
                {"tipo": TipoItemFicha.PASTILLAS, "precio": 32_000},
                {"tipo": TipoItemFicha.OBRA_MANO, "precio": 15_000},
            ),
        )

        self.assertEqual(self.orden.items.count(), 2)
        self.assertEqual(self.orden.total, 47_000)

    def test_borra_una_linea_sin_tocar_las_demas(self) -> None:
        self.client.post(
            self._url(),
            self._payload(
                {"tipo": TipoItemFicha.PASTILLAS, "precio": 32_000},
                {"tipo": TipoItemFicha.OBRA_MANO, "precio": 15_000, "DELETE": True},
            ),
        )

        lineas = self._lineas_guardadas()
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0].tipo, TipoItemFicha.PASTILLAS)

    def test_guarda_los_datos_del_repuesto_de_la_linea(self) -> None:
        self.client.post(
            self._url(),
            self._payload(
                {
                    "tipo": TipoItemFicha.PASTILLAS,
                    "precio": 32_000,
                    "detalle": "trasero",
                    "codigo_repuesto": "23479",
                    "marca_repuesto": "Bosch",
                }
            ),
        )

        linea = self._lineas_guardadas()[0]
        self.assertEqual(linea.detalle, "trasero")
        self.assertEqual(linea.codigo_repuesto, "23479")
        self.assertEqual(linea.marca_repuesto, "Bosch")

    def test_corrige_las_observaciones_de_la_ficha(self) -> None:
        self.client.post(
            self._url(),
            self._payload(
                {"tipo": TipoItemFicha.PASTILLAS, "precio": 32_000},
                observaciones="Se cambió el juego completo.",
            ),
        )

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.observaciones, "Se cambió el juego completo.")

    # -- Integridad de la visita -------------------------------------------

    def test_el_total_lo_calcula_el_servidor_y_no_el_navegador(self) -> None:
        self.client.post(
            self._url(),
            self._payload(
                {"tipo": TipoItemFicha.PASTILLAS, "precio": 5_000},
                **{"total": "999999", "lineas-TOTAL": "999999"},
            ),
        )

        self.assertEqual(self.orden.total, 5_000)

    def test_no_permite_cambiar_la_fecha_ni_el_kilometraje_de_la_visita(self) -> None:
        self.client.post(
            self._url(),
            self._payload(
                {"tipo": TipoItemFicha.PASTILLAS, "precio": 32_000},
                fecha_ingreso="2020-01-01",
                kilometraje="1",
            ),
        )

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.fecha_ingreso, self.fecha)
        self.assertEqual(self.orden.kilometraje, 78_400)

    def test_rechaza_dejar_la_ficha_sin_lineas_y_conserva_la_original(self) -> None:
        respuesta = self.client.post(self._url(), self._payload())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Agrega al menos una línea")
        self.assertEqual(self.orden.items.count(), 1)
        self.assertEqual(self.orden.total, 32_000)

    def test_una_visita_inexistente_devuelve_404(self) -> None:
        respuesta = self.client.get(reverse("workshop:ficha_editar", args=[999_999]))

        self.assertEqual(respuesta.status_code, 404)

    # -- Presentación y acceso ---------------------------------------------

    def test_muestra_las_lineas_guardadas_al_abrir_la_pantalla(self) -> None:
        respuesta = self.client.get(self._url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Corregir ficha")
        self.assertContains(respuesta, "32.000")

    def test_sin_sesion_iniciada_exige_ingresar(self) -> None:
        self.client.logout()

        respuesta = self.client.get(self._url())

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("accounts:login"), respuesta.url)

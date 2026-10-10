"""
Pruebas del aviso de patente ya registrada en la pantalla de ingreso.

Cubren las dos mitades: el selector que resuelve si el auto ya vino y el
endpoint JSON que alimenta la tarjeta del formulario.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.workshop.models import Cliente, ItemTrabajo, OrdenTrabajo, TipoItemFicha, Vehiculo
from apps.workshop.selectors import vehiculo_ya_registrado

EMAIL = "recepcion@taller.cl"
CLAVE = "clave-de-prueba-1234"


class VehiculoYaRegistradoTests(TestCase):
    """El selector que decide si hay algo que avisar."""

    def setUp(self) -> None:
        self.cliente = Cliente.objects.create(nombre="María Rojas", telefono="+56 9 8123 4567")
        self.vehiculo = Vehiculo.objects.create(
            patente="BJDF45",
            cliente=self.cliente,
            marca="Toyota",
            modelo="Yaris",
            anio=2018,
        )

    def _visita(self, dias_atras: int, precio: int) -> OrdenTrabajo:
        orden = OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo,
            fecha_ingreso=timezone.localdate() - timedelta(days=dias_atras),
        )
        ItemTrabajo.objects.create(
            orden=orden, tipo=TipoItemFicha.PASTILLAS, precio=precio, detalle="trasero"
        )
        return orden

    def test_encuentra_el_auto_por_su_patente_exacta(self) -> None:
        registrado = vehiculo_ya_registrado("BJDF45")

        self.assertIsNotNone(registrado)
        self.assertEqual(registrado.vehiculo.patente, "BJDF45")
        self.assertEqual(registrado.cliente.nombre, "María Rojas")

    def test_encuentra_el_auto_aunque_la_patente_venga_con_separadores(self) -> None:
        self.assertIsNotNone(vehiculo_ya_registrado(" bjd-f45 "))

    def test_una_patente_desconocida_no_avisa_nada(self) -> None:
        self.assertIsNone(vehiculo_ya_registrado("ZZZZ11"))

    def test_una_patente_invalida_no_avisa_nada(self) -> None:
        """Mientras la patente no es un dato confiable, no se consulta nada."""
        for patente in ("", "AB", "123456", "ABCDEFGH"):
            with self.subTest(patente=patente):
                self.assertIsNone(vehiculo_ya_registrado(patente))

    def test_cuenta_las_visitas_y_trae_la_mas_reciente(self) -> None:
        self._visita(dias_atras=120, precio=30_000)
        reciente = self._visita(dias_atras=10, precio=45_000)

        registrado = vehiculo_ya_registrado("BJDF45")

        self.assertEqual(registrado.total_visitas, 2)
        self.assertEqual(registrado.ultima_orden.pk, reciente.pk)

    def test_un_auto_sin_visitas_no_tiene_ultima_orden(self) -> None:
        registrado = vehiculo_ya_registrado("BJDF45")

        self.assertEqual(registrado.total_visitas, 0)
        self.assertIsNone(registrado.ultima_orden)

    def test_la_descripcion_cae_en_un_texto_de_reemplazo_sin_marca(self) -> None:
        self.vehiculo.marca = ""
        self.vehiculo.modelo = ""
        self.vehiculo.anio = None
        self.vehiculo.save()

        self.assertEqual(vehiculo_ya_registrado("BJDF45").descripcion, "Sin datos de modelo")


class PatenteEstadoTests(TestCase):
    """El endpoint JSON que alimenta la tarjeta del formulario."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(email=EMAIL, password=CLAVE, full_name="Encargada")
        self.cliente = Cliente.objects.create(nombre="María Rojas", telefono="+56 9 8123 4567")
        self.vehiculo = Vehiculo.objects.create(
            patente="BJDF45",
            cliente=self.cliente,
            marca="Toyota",
            modelo="Yaris",
            anio=2018,
        )
        self.client.force_login(self.user)

    def _url(self) -> str:
        return reverse("workshop:patente_estado")

    def _get(self, patente: str) -> dict:
        respuesta = self.client.get(self._url(), {"patente": patente})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/json")
        return json.loads(respuesta.content)

    def test_informa_patente_descripcion_y_dueno(self) -> None:
        datos = self._get("BJDF45")

        self.assertTrue(datos["registrado"])
        self.assertEqual(datos["patente"], "BJDF45")
        self.assertEqual(datos["descripcion"], "Toyota Yaris 2018")
        self.assertEqual(datos["cliente"]["nombre"], "María Rojas")
        # El teléfono viaja crudo para rellenar el campo y legible para mostrar.
        self.assertEqual(datos["cliente"]["telefono"], "56981234567")
        self.assertEqual(datos["cliente"]["telefono_legible"], "+56 9 8123 4567")
        self.assertEqual(datos["cliente"]["email"], "")

    def test_informa_las_visitas_y_la_ultima_con_su_total(self) -> None:
        orden = OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo,
            fecha_ingreso=timezone.localdate() - timedelta(days=30),
        )
        ItemTrabajo.objects.create(orden=orden, tipo=TipoItemFicha.PASTILLAS, precio=32_000)
        ItemTrabajo.objects.create(orden=orden, tipo=TipoItemFicha.OBRA_MANO, precio=25_000)

        datos = self._get("BJDF45")

        self.assertEqual(datos["total_visitas"], 1)
        self.assertEqual(datos["ultima_visita"]["total"], 57_000)
        self.assertEqual(datos["ultima_visita"]["trabajos"], "Pastillas, Obra de Mano")
        fecha = (timezone.localdate() - timedelta(days=30)).strftime("%d-%m-%Y")
        self.assertEqual(datos["ultima_visita"]["fecha"], fecha)

    def test_un_auto_sin_visitas_informa_la_ultima_como_nula(self) -> None:
        datos = self._get("BJDF45")

        self.assertEqual(datos["total_visitas"], 0)
        self.assertIsNone(datos["ultima_visita"])

    def test_entrega_el_enlace_a_la_ficha_del_vehiculo(self) -> None:
        datos = self._get("BJDF45")

        self.assertEqual(datos["url_ficha"], reverse("workshop:vehiculo", args=["BJDF45"]))

    def test_una_patente_desconocida_no_esta_registrada(self) -> None:
        self.assertEqual(self._get("ZZZZ11"), {"registrado": False})

    def test_una_patente_invalida_no_esta_registrada(self) -> None:
        self.assertEqual(self._get("12"), {"registrado": False})

    def test_sin_parametro_patente_responde_que_no_esta_registrada(self) -> None:
        respuesta = self.client.get(self._url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(json.loads(respuesta.content), {"registrado": False})

    def test_acepta_la_patente_en_minusculas_y_con_separadores(self) -> None:
        self.assertTrue(self._get("bjd-f45")["registrado"])

    def test_sin_sesion_iniciada_no_entrega_datos_del_dueno(self) -> None:
        """El aviso muestra nombre y teléfono: no puede quedar público."""
        self.client.logout()

        respuesta = self.client.get(self._url(), {"patente": "BJDF45"})

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("accounts:login"), respuesta.url)


class AvisoEnElFormularioTests(TestCase):
    """Lo que la pantalla de ingreso necesita para que el aviso funcione."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(email=EMAIL, password=CLAVE, full_name="Encargada")
        self.client.force_login(self.user)

    def test_el_formulario_trae_el_contenedor_y_la_tarjeta(self) -> None:
        respuesta = self.client.get(reverse("workshop:ingreso_create"))
        html = respuesta.content.decode()

        self.assertIn("data-aviso-patente", html)
        self.assertIn("plantilla-aviso-patente", html)
        self.assertIn(reverse("workshop:patente_estado"), html)
        self.assertIn("js/patente.js", html)

    def test_el_aviso_arranca_oculto(self) -> None:
        """Sin JavaScript no debe quedar una tarjeta vacía a la vista."""
        respuesta = self.client.get(reverse("workshop:ingreso_create"))

        self.assertContains(respuesta, "data-aviso-patente")
        self.assertContains(respuesta, "hidden")

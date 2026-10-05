"""Pruebas de las vistas del taller."""

from __future__ import annotations

from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.workshop.models import Cliente, ItemTrabajo, OrdenTrabajo, TipoItemFicha, Vehiculo
from apps.workshop.tests.helpers import payload_lineas

EMAIL = "recepcion@taller.cl"
CLAVE = "clave-de-prueba-1234"


class BaseAutenticadaTests(TestCase):
    """Base con un usuario con sesión iniciada y datos de ejemplo."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(email=EMAIL, password=CLAVE, full_name="Encargada")
        self.client.force_login(self.user)

        self.cliente = Cliente.objects.create(nombre="María Rojas", telefono="+56 9 8123 4567")
        self.vehiculo = Vehiculo.objects.create(
            patente="BJDF45",
            cliente=self.cliente,
            marca="Toyota",
            modelo="Yaris",
            anio=2018,
        )

    def crear_orden(self, **overrides) -> OrdenTrabajo:
        datos = {
            "vehiculo": self.vehiculo,
            "fecha_ingreso": timezone.localdate() - timedelta(days=30),
            "kilometraje": 78_400,
        }
        return OrdenTrabajo.objects.create(**{**datos, **overrides})


class BuscarTests(BaseAutenticadaTests):
    def test_sin_termino_muestra_los_ultimos_ingresos(self) -> None:
        self.crear_orden()

        respuesta = self.client.get(reverse("workshop:buscar"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "BJDF45")
        self.assertContains(respuesta, "Últimos ingresos")

    def test_sin_ingresos_invita_a_registrar_el_primero(self) -> None:
        respuesta = self.client.get(reverse("workshop:buscar"))

        self.assertContains(respuesta, "Todavía no hay ingresos registrados")

    def test_encuentra_por_patente_completa(self) -> None:
        respuesta = self.client.get(reverse("workshop:buscar"), {"patente": "BJDF45"})

        self.assertContains(respuesta, "BJDF45")
        self.assertContains(respuesta, "Toyota Yaris")

    def test_encuentra_ignorando_mayusculas_y_separadores(self) -> None:
        respuesta = self.client.get(reverse("workshop:buscar"), {"patente": "bjd-f45"})

        self.assertContains(respuesta, "1 resultado")

    def test_encuentra_con_un_fragmento_de_la_patente(self) -> None:
        respuesta = self.client.get(reverse("workshop:buscar"), {"patente": "JDF"})

        self.assertContains(respuesta, "BJDF45")

    def test_una_patente_desconocida_ofrece_registrarla(self) -> None:
        respuesta = self.client.get(reverse("workshop:buscar"), {"patente": "ZZZZ11"})

        self.assertContains(respuesta, "no está registrada")
        self.assertContains(respuesta, reverse("workshop:ingreso_create"))


class FichaVehiculoTests(BaseAutenticadaTests):
    def test_muestra_el_historial_y_la_proxima_mantencion(self) -> None:
        orden = self.crear_orden(proxima_mantencion_km=90_000)
        ItemTrabajo.objects.create(orden=orden, tipo=TipoItemFicha.PASTILLAS, precio=32_000)

        respuesta = self.client.get(reverse("workshop:vehiculo", args=["BJDF45"]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Pastillas")
        self.assertContains(respuesta, "María Rojas")
        # El resumen se calcula a partir de la última visita, no de todo el historial.
        self.assertEqual(respuesta.context["resumen"].proxima_mantencion_km, 90_000)
        self.assertEqual(respuesta.context["resumen"].total_visitas, 1)

    def test_una_patente_inexistente_devuelve_404(self) -> None:
        respuesta = self.client.get(reverse("workshop:vehiculo", args=["ZZZZ11"]))

        self.assertEqual(respuesta.status_code, 404)

    def test_acepta_la_patente_en_minusculas(self) -> None:
        respuesta = self.client.get(reverse("workshop:vehiculo", args=["bjdf45"]))

        self.assertEqual(respuesta.status_code, 200)

    def test_un_vehiculo_sin_visitas_lo_indica(self) -> None:
        respuesta = self.client.get(reverse("workshop:vehiculo", args=["BJDF45"]))

        self.assertContains(respuesta, "todavía no tiene visitas registradas")

    def test_las_fechas_del_historial_se_muestran_en_español(self) -> None:
        self.crear_orden(fecha_ingreso=date(2026, 7, 29), kilometraje=78_400)

        respuesta = self.client.get(reverse("workshop:vehiculo", args=["BJDF45"]))

        self.assertContains(respuesta, "29 de julio de 2026")
        self.assertContains(respuesta, "78.400 km")

    def test_ignora_el_idioma_configurado_en_el_navegador(self) -> None:
        """El sistema es monolingüe: un navegador en inglés no debe cambiar los formatos."""
        self.crear_orden(fecha_ingreso=date(2026, 7, 29))

        respuesta = self.client.get(
            reverse("workshop:vehiculo", args=["BJDF45"]),
            headers={"accept-language": "en-US,en;q=0.9"},
        )

        self.assertContains(respuesta, "29 de julio de 2026")


class FichaClienteTests(BaseAutenticadaTests):
    def test_lista_los_vehiculos_del_cliente(self) -> None:
        Vehiculo.objects.create(patente="KLMN91", cliente=self.cliente, marca="Suzuki")

        respuesta = self.client.get(reverse("workshop:cliente", args=[self.cliente.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "BJDF45")
        self.assertContains(respuesta, "KLMN91")
        # El enlace usa el número normalizado; en pantalla se muestra legible.
        self.assertContains(respuesta, "wa.me/56981234567")
        self.assertContains(respuesta, "+56 9 8123 4567")


class FugasDePlantillaTests(BaseAutenticadaTests):
    """
    Ninguna página debe mostrar marcadores de plantilla como texto.

    Django solo reconoce ``{# ... #}`` cuando el comentario abre y cierra en la
    misma línea; un ``{#`` suelto se imprime tal cual y aparece en pantalla. Lo
    mismo vale para ``{%`` y ``{{``. Estas pruebas recorren las pantallas del
    taller para que el error se vea antes de llegar al mesón.
    """

    def _marcadores(self, html: str) -> list[str]:
        return [marcador for marcador in ("{#", "{%", "{{") if marcador in html]

    def _paginas(self) -> dict[str, str]:
        orden = self.crear_orden()
        return {
            "buscar": reverse("workshop:buscar"),
            "ingreso": reverse("workshop:ingreso_create"),
            "vehiculo": reverse("workshop:vehiculo", args=[self.vehiculo.patente]),
            "cliente": reverse("workshop:cliente", args=[self.cliente.pk]),
            "editar": reverse("workshop:ficha_editar", args=[orden.pk]),
            "imprimir": reverse("workshop:ficha_imprimir", args=[orden.pk]),
        }

    def test_las_pantallas_no_muestran_marcadores_de_plantilla(self) -> None:
        for nombre, ruta in self._paginas().items():
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(ruta)

                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(self._marcadores(respuesta.content.decode()), [])

    def test_el_formulario_con_errores_tampoco_los_muestra(self) -> None:
        respuesta = self.client.post(
            reverse("workshop:ingreso_create"),
            {"patente": "123456"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._marcadores(respuesta.content.decode()), [])


class RegistroIngresoTests(BaseAutenticadaTests):
    def _payload(self, **overrides) -> dict[str, object]:
        datos: dict[str, object] = {
            "patente": "WXYZ99",
            "marca": "Chevrolet",
            "modelo": "Sail",
            "anio": 2016,
            "color": "Gris",
            "cliente_nombre": "Pedro Muñoz",
            "cliente_telefono": "+56 9 6543 2109",
            "cliente_email": "",
            "fecha_ingreso": timezone.localdate().isoformat(),
            "kilometraje": 132_000,
            "observaciones": "Cáliper pegado.",
            "proxima_mantencion_km": 150_000,
            "proxima_mantencion_fecha": "",
            **payload_lineas(
                {"tipo": TipoItemFicha.REP_CALIPER, "precio": 68_000, "detalle": "delantero"},
            ),
        }
        return {**datos, **overrides}

    def test_precarga_la_patente_desde_la_url(self) -> None:
        respuesta = self.client.get(reverse("workshop:ingreso_create"), {"patente": "abcd12"})

        self.assertContains(respuesta, 'value="ABCD12"')

    def test_la_casilla_de_borrado_queda_oculta_detras_de_un_boton(self) -> None:
        """La línea se quita con un botón, no marcando una casilla a la vista."""
        respuesta = self.client.get(reverse("workshop:ingreso_create"))

        html = respuesta.content.decode()
        self.assertIn("data-quitar-linea", html)
        self.assertIn("campo-borrar", html)
        # La casilla viaja igual en el formulario (es el contrato con Django),
        # pero fuera de la vista y sin recibir el foco.
        self.assertIn("-DELETE", html)
        self.assertIn('tabindex="-1"', html)

    def test_registra_el_ingreso_y_redirige_a_la_ficha(self) -> None:
        respuesta = self.client.post(reverse("workshop:ingreso_create"), self._payload())

        self.assertRedirects(respuesta, reverse("workshop:vehiculo", args=["WXYZ99"]))
        self.assertTrue(Vehiculo.objects.filter(patente="WXYZ99").exists())
        self.assertEqual(ItemTrabajo.objects.filter(orden__vehiculo__patente="WXYZ99").count(), 1)

    def test_rechaza_un_ingreso_sin_ninguna_linea(self) -> None:
        respuesta = self.client.post(
            reverse("workshop:ingreso_create"),
            self._payload(**payload_lineas()),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Agrega al menos una línea")
        self.assertFalse(Vehiculo.objects.filter(patente="WXYZ99").exists())

    def test_registra_el_ingreso_aunque_sobre_una_fila_en_blanco(self) -> None:
        respuesta = self.client.post(
            reverse("workshop:ingreso_create"),
            self._payload(
                **payload_lineas(
                    {"tipo": TipoItemFicha.PASTILLAS, "precio": 32_000},
                    blancas=1,
                )
            ),
        )

        self.assertRedirects(respuesta, reverse("workshop:vehiculo", args=["WXYZ99"]))
        self.assertEqual(ItemTrabajo.objects.filter(orden__vehiculo__patente="WXYZ99").count(), 1)

    def test_reutiliza_el_cliente_si_el_telefono_ya_existe(self) -> None:
        self.client.post(
            reverse("workshop:ingreso_create"),
            self._payload(
                patente="WXYZ99",
                cliente_telefono="+56 9 8123 4567",
                cliente_nombre="María Rojas",
            ),
        )

        self.assertEqual(Cliente.objects.count(), 1)

    def test_una_patente_invalida_no_registra_nada(self) -> None:
        respuesta = self.client.post(
            reverse("workshop:ingreso_create"), self._payload(patente="123456")
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Revisa la patente")
        self.assertFalse(Vehiculo.objects.filter(patente="123456").exists())

    def test_avisa_cuando_intenta_registrar_la_misma_visita_dos_veces(self) -> None:
        self.client.post(reverse("workshop:ingreso_create"), self._payload())
        respuesta = self.client.post(reverse("workshop:ingreso_create"), self._payload())

        self.assertRedirects(respuesta, reverse("workshop:vehiculo", args=["WXYZ99"]))
        self.assertEqual(OrdenTrabajo.objects.filter(vehiculo__patente="WXYZ99").count(), 1)

    def test_rechaza_una_proxima_mantencion_anterior_al_ingreso(self) -> None:
        hoy = timezone.localdate()

        respuesta = self.client.post(
            reverse("workshop:ingreso_create"),
            self._payload(
                fecha_ingreso=hoy.isoformat(),
                proxima_mantencion_fecha=(hoy - timedelta(days=1)).isoformat(),
            ),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "debe ser posterior a la fecha de ingreso")

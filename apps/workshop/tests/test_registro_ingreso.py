"""Pruebas del servicio de registro de ingresos."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.workshop.exceptions import (
    FichaVaciaError,
    IngresoDuplicadoError,
    LineaFichaInvalidaError,
    PatenteInvalidaError,
    TotalFichaNegativoError,
)
from apps.workshop.models import (
    TOPE_PRECIO,
    Cliente,
    ItemTrabajo,
    OrdenTrabajo,
    TipoItemFicha,
    Vehiculo,
)
from apps.workshop.services import (
    DatosIngreso,
    LineaFicha,
    RegistroIngresoService,
)

LINEA_BASE = LineaFicha(tipo=TipoItemFicha.OBRA_MANO, precio=10_000)


class RegistroIngresoServiceTests(TestCase):
    def setUp(self) -> None:
        self.service = RegistroIngresoService()
        self.hoy = timezone.localdate()

    def _datos(self, **overrides) -> DatosIngreso:
        base = {
            "patente": "ABCD12",
            "cliente_nombre": "María Rojas",
            "cliente_telefono": "+56 9 8123 4567",
            "kilometraje": 85_000,
            "fecha_ingreso": self.hoy,
            "lineas": (LINEA_BASE,),
        }
        return DatosIngreso(**{**base, **overrides})

    # -- Camino feliz -------------------------------------------------------

    def test_crea_cliente_vehiculo_orden_y_trabajos(self) -> None:
        datos = self._datos(
            marca="Toyota",
            modelo="Yaris",
            anio=2018,
            lineas=(
                LineaFicha(tipo=TipoItemFicha.PASTILLAS, precio=32_000, detalle="delantero"),
                LineaFicha(tipo=TipoItemFicha.OBRA_MANO, precio=25_000),
            ),
        )

        resultado = self.service.registrar(datos)

        self.assertTrue(resultado.cliente_creado)
        self.assertTrue(resultado.vehiculo_creado)
        self.assertEqual(resultado.vehiculo.patente, "ABCD12")
        self.assertEqual(resultado.vehiculo.descripcion_corta, "Toyota Yaris 2018")
        self.assertEqual(resultado.orden.kilometraje, 85_000)
        self.assertEqual(
            set(resultado.orden.items.values_list("tipo", flat=True)),
            {TipoItemFicha.PASTILLAS, TipoItemFicha.OBRA_MANO},
        )

    def test_guarda_el_detalle_el_codigo_la_marca_y_el_precio_de_cada_linea(self) -> None:
        datos = self._datos(
            lineas=(
                LineaFicha(
                    tipo=TipoItemFicha.PASTILLAS,
                    precio=32_000,
                    detalle="trasero",
                    codigo_repuesto=" 23479 ",
                    marca_repuesto="Bosch",
                ),
            )
        )

        resultado = self.service.registrar(datos)

        linea = resultado.orden.items.get()
        self.assertEqual(linea.detalle, "trasero")
        self.assertEqual(linea.codigo_repuesto, "23479")
        self.assertEqual(linea.marca_repuesto, "Bosch")
        self.assertEqual(linea.precio, 32_000)

    def test_el_total_es_la_suma_de_las_lineas_menos_el_descuento(self) -> None:
        resultado = self.service.registrar(
            self._datos(
                lineas=(
                    LineaFicha(tipo=TipoItemFicha.PASTILLAS, precio=32_000),
                    LineaFicha(tipo=TipoItemFicha.OBRA_MANO, precio=25_000),
                    LineaFicha(
                        tipo=TipoItemFicha.DESCUENTO,
                        precio=-7_000,
                        detalle="cliente frecuente",
                    ),
                )
            )
        )

        self.assertEqual(resultado.orden.total, 50_000)

    def test_normaliza_la_patente_y_el_telefono_antes_de_guardar(self) -> None:
        resultado = self.service.registrar(self._datos(patente=" ab-cd 12 "))

        self.assertEqual(resultado.vehiculo.patente, "ABCD12")
        self.assertEqual(resultado.cliente.telefono, "56981234567")

    def test_permite_repetir_el_mismo_trabajo_en_una_visita(self) -> None:
        """Cambiar las pastillas delanteras y traseras son dos líneas distintas."""
        datos = self._datos(
            lineas=(
                LineaFicha(tipo=TipoItemFicha.PASTILLAS, precio=32_000, detalle="delantero"),
                LineaFicha(tipo=TipoItemFicha.PASTILLAS, precio=29_000, detalle="trasero"),
            )
        )

        resultado = self.service.registrar(datos)

        self.assertEqual(resultado.orden.items.count(), 2)
        self.assertEqual(resultado.orden.total, 61_000)

    # -- Reutilización de entidades ----------------------------------------

    def test_reutiliza_el_cliente_cuando_el_telefono_ya_existe(self) -> None:
        primero = self.service.registrar(self._datos(patente="ABCD12"))

        segundo = self.service.registrar(
            self._datos(
                patente="WXYZ99",
                cliente_telefono="981234567",  # misma persona, otro formato
                cliente_nombre="María Rojas Soto",
                kilometraje=120_000,
            )
        )

        self.assertFalse(segundo.cliente_creado)
        self.assertEqual(segundo.cliente.pk, primero.cliente.pk)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_agrega_una_nueva_visita_al_vehiculo_existente(self) -> None:
        primero = self.service.registrar(self._datos())

        segunda = self.service.registrar(
            self._datos(kilometraje=95_000, fecha_ingreso=self.hoy + timedelta(days=30))
        )

        self.assertFalse(segunda.vehiculo_creado)
        self.assertEqual(segunda.vehiculo.pk, primero.vehiculo.pk)
        self.assertEqual(Vehiculo.objects.count(), 1)
        self.assertEqual(segunda.vehiculo.ordenes.count(), 2)

    def test_conserva_el_dueño_original_aunque_cambie_el_nombre_ingresado(self) -> None:
        original = self.service.registrar(self._datos())

        self.service.registrar(
            self._datos(
                cliente_telefono="+56 9 9999 8888",
                cliente_nombre="Otro Conductor",
                kilometraje=99_000,
            )
        )

        original.vehiculo.refresh_from_db()
        self.assertEqual(original.vehiculo.cliente_id, original.cliente.pk)

    def test_completa_datos_del_vehiculo_sin_borrar_los_existentes(self) -> None:
        primer_resultado = self.service.registrar(self._datos(marca="Toyota", modelo="Yaris"))

        self.service.registrar(self._datos(marca="", modelo="", kilometraje=90_000))

        primer_resultado.vehiculo.refresh_from_db()
        self.assertEqual(primer_resultado.vehiculo.marca, "Toyota")
        self.assertEqual(primer_resultado.vehiculo.modelo, "Yaris")

    # -- Reglas de integridad ----------------------------------------------

    def test_rechaza_una_patente_con_formato_invalido(self) -> None:
        with self.assertRaises(PatenteInvalidaError):
            self.service.registrar(self._datos(patente="123456"))

        self.assertFalse(Cliente.objects.exists())
        self.assertFalse(Vehiculo.objects.exists())

    def test_bloquea_un_ingreso_repetido_con_la_misma_fecha_y_kilometraje(self) -> None:
        primero = self.service.registrar(self._datos())

        with self.assertRaises(IngresoDuplicadoError) as contexto:
            self.service.registrar(self._datos())

        self.assertEqual(contexto.exception.orden_id, primero.orden.pk)
        self.assertEqual(OrdenTrabajo.objects.count(), 1)

    def test_registra_la_proxima_mantencion_recomendada(self) -> None:
        resultado = self.service.registrar(
            self._datos(
                proxima_mantencion_km=100_000,
                proxima_mantencion_fecha=self.hoy + timedelta(days=180),
            )
        )

        self.assertTrue(resultado.orden.tiene_proxima_mantencion)
        self.assertEqual(resultado.orden.proxima_mantencion_km, 100_000)

    def test_los_items_quedan_asociados_a_la_orden_creada(self) -> None:
        resultado = self.service.registrar(
            self._datos(lineas=(LineaFicha(tipo=TipoItemFicha.REP_BOMBA, precio=45_000),))
        )

        self.assertEqual(ItemTrabajo.objects.filter(orden=resultado.orden).count(), 1)

    # -- Reglas de las líneas de la ficha ----------------------------------

    def test_rechaza_una_ficha_sin_lineas(self) -> None:
        with self.assertRaises(FichaVaciaError):
            self.service.registrar(self._datos(lineas=()))

        self.assertFalse(OrdenTrabajo.objects.exists())

    def test_rechaza_un_trabajo_que_no_esta_en_el_catalogo(self) -> None:
        with self.assertRaises(LineaFichaInvalidaError):
            self.service.registrar(
                self._datos(lineas=(LineaFicha(tipo="cambiar_el_aceite", precio=5_000),))
            )

    def test_rechaza_un_monto_negativo_fuera_de_la_linea_de_descuento(self) -> None:
        with self.assertRaises(LineaFichaInvalidaError):
            self.service.registrar(
                self._datos(lineas=(LineaFicha(tipo=TipoItemFicha.PASTILLAS, precio=-1_000),))
            )

    def test_rechaza_un_precio_fuera_del_rango_permitido(self) -> None:
        with self.assertRaises(LineaFichaInvalidaError):
            self.service.registrar(
                self._datos(
                    lineas=(LineaFicha(tipo=TipoItemFicha.OBRA_MANO, precio=TOPE_PRECIO + 1),)
                )
            )

    def test_rechaza_un_descuento_mayor_que_el_trabajo(self) -> None:
        with self.assertRaises(TotalFichaNegativoError):
            self.service.registrar(
                self._datos(
                    lineas=(
                        LineaFicha(tipo=TipoItemFicha.OBRA_MANO, precio=10_000),
                        LineaFicha(tipo=TipoItemFicha.DESCUENTO, precio=-15_000),
                    )
                )
            )

        self.assertFalse(Cliente.objects.exists())

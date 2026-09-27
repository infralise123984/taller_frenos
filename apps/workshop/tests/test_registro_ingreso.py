"""Pruebas del servicio de registro de ingresos."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.workshop.exceptions import IngresoDuplicadoError, PatenteInvalidaError
from apps.workshop.models import Cliente, ItemTrabajo, OrdenTrabajo, TipoTrabajo, Vehiculo
from apps.workshop.services import (
    DatosIngreso,
    RegistroIngresoService,
    TrabajoSolicitado,
)


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
        }
        return DatosIngreso(**{**base, **overrides})

    # -- Camino feliz -------------------------------------------------------

    def test_crea_cliente_vehiculo_orden_y_trabajos(self) -> None:
        datos = self._datos(
            marca="Toyota",
            modelo="Yaris",
            anio=2018,
            trabajos=(
                TrabajoSolicitado(tipo=TipoTrabajo.CAMBIO_PASTILLAS),
                TrabajoSolicitado(tipo=TipoTrabajo.PURGA),
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
            {TipoTrabajo.CAMBIO_PASTILLAS, TipoTrabajo.PURGA},
        )

    def test_normaliza_la_patente_y_el_telefono_antes_de_guardar(self) -> None:
        resultado = self.service.registrar(self._datos(patente=" ab-cd 12 "))

        self.assertEqual(resultado.vehiculo.patente, "ABCD12")
        self.assertEqual(resultado.cliente.telefono, "56981234567")

    def test_no_crea_trabajos_duplicados_en_la_misma_visita(self) -> None:
        datos = self._datos(
            trabajos=(
                TrabajoSolicitado(tipo=TipoTrabajo.PURGA),
                TrabajoSolicitado(tipo=TipoTrabajo.PURGA),
            )
        )

        resultado = self.service.registrar(datos)

        self.assertEqual(resultado.orden.items.count(), 1)

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
            self._datos(trabajos=(TrabajoSolicitado(tipo=TipoTrabajo.REVISION),))
        )

        self.assertEqual(ItemTrabajo.objects.filter(orden=resultado.orden).count(), 1)

"""
Carga datos de demostración para recorrer las pantallas del mockup.

Es idempotente: puede ejecutarse varias veces sin duplicar registros.

Uso:
    python manage.py seed_demo
    python manage.py seed_demo --email recepcion@taller.cl --password "..." --reset
"""

from __future__ import annotations

import os
import secrets
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.workshop.models import Cliente, ItemTrabajo, OrdenTrabajo, TipoTrabajo, Vehiculo
from apps.workshop.telefonos import normalize_telefono

CLIENTES_DEMO = [
    {
        "nombre": "María Fernanda Rojas",
        "telefono": "+56 9 8123 4567",
        "email": "mf.rojas@ejemplo.cl",
        "vehiculos": [
            {
                "patente": "BJDF45",
                "marca": "Toyota",
                "modelo": "Yaris",
                "anio": 2018,
                "color": "Rojo",
            },
            {
                "patente": "KLMN91",
                "marca": "Suzuki",
                "modelo": "Swift",
                "anio": 2021,
                "color": "Blanco",
            },
        ],
    },
    {
        "nombre": "Pedro Antonio Muñoz",
        "telefono": "+56 9 6543 2109",
        "email": "",
        "vehiculos": [
            {
                "patente": "RTWX22",
                "marca": "Chevrolet",
                "modelo": "Sail",
                "anio": 2016,
                "color": "Gris",
            },
        ],
    },
]

# (patente, días atrás, kilometraje, tipos, observaciones, próxima km, próxima días)
VISITAS_DEMO = [
    (
        "BJDF45",
        240,
        78_400,
        [TipoTrabajo.CAMBIO_PASTILLAS, TipoTrabajo.RECTIFICADO_DISCOS],
        "Pastillas delanteras y rectificado de discos. Cliente reporta chirrido al frenar.",
        90_000,
        120,
    ),
    (
        "BJDF45",
        60,
        88_900,
        [TipoTrabajo.REVISION, TipoTrabajo.PURGA],
        "Revisión general preventiva. Se purgó el circuito y se completó líquido.",
        None,
        None,
    ),
    (
        "KLMN91",
        150,
        41_200,
        [TipoTrabajo.CAMBIO_LIQUIDO],
        "Cambio de líquido de frenos según pauta del fabricante.",
        60_000,
        210,
    ),
    (
        "RTWX22",
        30,
        132_000,
        [TipoTrabajo.REPARACION_CALIPERS, TipoTrabajo.CAMBIO_PASTILLAS],
        "Cáliper delantero izquierdo pegado; se reparó y se cambió el juego de pastillas.",
        150_000,
        90,
    ),
]


class Command(BaseCommand):
    help = "Crea usuarios y datos de taller de ejemplo para revisar las pantallas."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--email", default="taller@ejemplo.cl", help="Correo del usuario de acceso."
        )
        parser.add_argument(
            "--password",
            default=os.environ.get("DEMO_PASSWORD", ""),
            help="Contraseña del usuario. Si se omite, se genera una aleatoria.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina los datos de demostración antes de volver a crearlos.",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        if options["reset"]:
            self._reset()
        self._crear_usuario(options["email"], options["password"])
        self._crear_datos_taller()

        self.stdout.write(self.style.SUCCESS("Datos de demostración listos."))

    # -- Usuario -----------------------------------------------------------

    def _crear_usuario(self, email: str, password: str) -> None:
        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(f"El usuario {email} ya existe; no se modificó su contraseña.")
            return

        if not password:
            password = secrets.token_urlsafe(12)
            generada = True
        else:
            generada = False

        User.objects.create_superuser(
            email=email, password=password, full_name="Encargada del taller"
        )

        self.stdout.write(self.style.WARNING(f"Usuario creado: {email}"))
        if generada:
            self.stdout.write(
                self.style.WARNING(
                    f"Contraseña generada (guárdala ahora, no se vuelve a mostrar): {password}"
                )
            )

    # -- Datos del taller --------------------------------------------------

    def _crear_datos_taller(self) -> None:
        creados = 0

        for datos_cliente in CLIENTES_DEMO:
            cliente, _ = Cliente.objects.get_or_create(
                telefono=normalize_telefono(datos_cliente["telefono"]),
                defaults={
                    "nombre": datos_cliente["nombre"],
                    "email": datos_cliente["email"],
                },
            )

            for datos_vehiculo in datos_cliente["vehiculos"]:
                vehiculo, creado = Vehiculo.objects.get_or_create(
                    patente=datos_vehiculo["patente"],
                    defaults={**datos_vehiculo, "cliente": cliente},
                )
                creados += int(creado)

        self._crear_visitas()
        self.stdout.write(f"Vehículos nuevos: {creados}")

    def _crear_visitas(self) -> None:
        hoy = timezone.localdate()

        for patente, dias_atras, km, tipos, observaciones, prox_km, prox_dias in VISITAS_DEMO:
            vehiculo = Vehiculo.objects.get(patente=patente)
            fecha = hoy - timedelta(days=dias_atras)

            orden, creada = OrdenTrabajo.objects.get_or_create(
                vehiculo=vehiculo,
                fecha_ingreso=fecha,
                kilometraje=km,
                defaults={
                    "observaciones": observaciones,
                    "proxima_mantencion_km": prox_km,
                    "proxima_mantencion_fecha": (fecha + timedelta(days=prox_dias))
                    if prox_dias
                    else None,
                },
            )
            if not creada:
                continue

            ItemTrabajo.objects.bulk_create([ItemTrabajo(orden=orden, tipo=tipo) for tipo in tipos])

    def _reset(self) -> None:
        """Elimina solo los datos de demostración, respetando el orden de dependencias."""
        patentes = [v["patente"] for c in CLIENTES_DEMO for v in c["vehiculos"]]
        telefonos = [normalize_telefono(c["telefono"]) for c in CLIENTES_DEMO]

        ItemTrabajo.objects.filter(orden__vehiculo__patente__in=patentes).delete()
        OrdenTrabajo.objects.filter(vehiculo__patente__in=patentes).delete()
        Vehiculo.objects.filter(patente__in=patentes).delete()
        Cliente.objects.filter(telefono__in=telefonos).delete()

        self.stdout.write(self.style.WARNING("Datos de demostración anteriores eliminados."))

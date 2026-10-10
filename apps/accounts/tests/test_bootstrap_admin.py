"""Pruebas del alta inicial segura del superusuario."""

from __future__ import annotations

import os
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import User

EMAIL = "admin@taller.cl"
PASSWORD = "Copper-Bridge-Window-2026!Guitar"


class BootstrapAdminTests(TestCase):
    def test_crea_superusuario_con_credenciales_del_entorno(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BOOTSTRAP_ADMIN_EMAIL": EMAIL,
                "BOOTSTRAP_ADMIN_PASSWORD": PASSWORD,
            },
            clear=True,
        ):
            call_command("bootstrap_admin")

        admin = User.objects.get(email=EMAIL)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password(PASSWORD))

    def test_exige_ambas_variables_de_entorno(self) -> None:
        with patch.dict(os.environ, {"BOOTSTRAP_ADMIN_EMAIL": EMAIL}, clear=True):
            with self.assertRaisesMessage(CommandError, "Define BOOTSTRAP_ADMIN_EMAIL"):
                call_command("bootstrap_admin")

        self.assertFalse(User.objects.exists())

    def test_rechaza_una_contrasena_que_no_cumple_los_validadores(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BOOTSTRAP_ADMIN_EMAIL": EMAIL,
                "BOOTSTRAP_ADMIN_PASSWORD": "short",
            },
            clear=True,
        ):
            with self.assertRaises(CommandError):
                call_command("bootstrap_admin")

        self.assertFalse(User.objects.exists())

    def test_no_crea_otra_cuenta_si_ya_hay_un_superusuario(self) -> None:
        existente = User.objects.create_superuser(
            email="existente@taller.cl",
            password=PASSWORD,
            full_name="Encargada",
        )

        with patch.dict(
            os.environ,
            {
                "BOOTSTRAP_ADMIN_EMAIL": EMAIL,
                "BOOTSTRAP_ADMIN_PASSWORD": "Another-Safe-Password-2026!Book",
            },
            clear=True,
        ):
            call_command("bootstrap_admin")

        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(existente.check_password(PASSWORD))

    def test_no_eleva_una_cuenta_existente_a_superusuario(self) -> None:
        existente = User.objects.create_user(email=EMAIL, password=PASSWORD)

        with patch.dict(
            os.environ,
            {
                "BOOTSTRAP_ADMIN_EMAIL": EMAIL,
                "BOOTSTRAP_ADMIN_PASSWORD": "Another-Safe-Password-2026!Book",
            },
            clear=True,
        ):
            with self.assertRaisesMessage(CommandError, "no se modificó ni se elevó"):
                call_command("bootstrap_admin")

        existente.refresh_from_db()
        self.assertFalse(existente.is_superuser)
        self.assertEqual(User.objects.count(), 1)

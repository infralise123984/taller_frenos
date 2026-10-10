"""Crea una sola cuenta administrativa inicial desde secretos del entorno."""

from __future__ import annotations

import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Crea el primer superusuario usando BOOTSTRAP_ADMIN_EMAIL y BOOTSTRAP_ADMIN_PASSWORD."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip()
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")

        if not email or not password:
            raise CommandError("Define BOOTSTRAP_ADMIN_EMAIL y BOOTSTRAP_ADMIN_PASSWORD juntos.")

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("Ya existe un superusuario; no se creó ni modificó ninguna cuenta.")
            return

        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                "El correo de bootstrap ya pertenece a una cuenta; no se modificó ni se elevó."
            )

        candidate = User(email=email, full_name="Administración")
        try:
            validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc

        User.objects.create_superuser(
            email=email,
            password=password,
            full_name="Administración",
        )
        self.stdout.write(
            "Cuenta administrativa inicial creada. Retira las variables de bootstrap del entorno."
        )

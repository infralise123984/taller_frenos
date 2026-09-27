"""Configuración de la app de gestión del taller."""

from django.apps import AppConfig


class WorkshopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.workshop"
    label = "workshop"
    verbose_name = "Gestión del taller"

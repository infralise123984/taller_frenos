#!/usr/bin/env python
"""Utilidad de línea de comandos de Django para tareas administrativas."""

import os
import sys


def main() -> None:
    """Ejecuta el comando de Django indicado por los argumentos del proceso."""
    # El archivo .env se carga dentro de config.settings.base vía django-environ.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - salvaguarda de entorno
        raise ImportError(
            "No se pudo importar Django. ¿Está activado el entorno virtual y "
            "ejecutaste 'pip install -r requirements/dev.txt'?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

"""
Configuración para desarrollo local.

Incluye valores por defecto inseguros que NUNCA deben usarse en producción.
"""

import base64
import hashlib

from .base import *  # noqa: F403

# Clave de desarrollo: predecible a propósito para que los clones nuevos del
# repositorio arranquen sin configuración previa.
if not SECRET_KEY:  # noqa: F405
    SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"  # noqa: S105

# Development-only key derivation. Production requires its own Fernet key.
if not TOTP_ENCRYPTION_KEY:  # noqa: F405
    TOTP_ENCRYPTION_KEY = base64.urlsafe_b64encode(
        hashlib.sha256(f"taller-totp:{SECRET_KEY}".encode()).digest()  # noqa: F405
    ).decode()

DEBUG = env.bool("DJANGO_DEBUG", default=True)  # noqa: F405

ALLOWED_HOSTS = env.list(  # noqa: F405
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "0.0.0.0", "[::1]"],  # noqa: S104
)

# En el mesón del taller se accede desde tablet/teléfono por red local, así que
# se permite el rango privado completo solo en desarrollo.
CSRF_TRUSTED_ORIGINS = env.list(  # noqa: F405
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[],
)

EMAIL_BACKEND = env(  # noqa: F405
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

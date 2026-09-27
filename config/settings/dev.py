"""
Configuración para desarrollo local.

Incluye valores por defecto inseguros que NUNCA deben usarse en producción.
"""

from .base import *  # noqa: F403

# Clave de desarrollo: predecible a propósito para que los clones nuevos del
# repositorio arranquen sin configuración previa.
if not SECRET_KEY:  # noqa: F405
    SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"  # noqa: S105

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

# El OTP se muestra en consola/logs y no requiere Supabase en desarrollo.
OTP_PROVIDER = env("OTP_PROVIDER", default="local")  # noqa: F405
EMAIL_BACKEND = env(  # noqa: F405
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

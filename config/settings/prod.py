"""
Configuración para producción.

Aplica "fail fast": si falta una variable crítica o una configuración queda en
modo inseguro, el proceso no arranca en lugar de exponer el sistema.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

# ---------------------------------------------------------------------------
# Validaciones de arranque
# ---------------------------------------------------------------------------

if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY es obligatoria en producción.")

if DEBUG:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_DEBUG no puede estar activo en producción.")

if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS debe declararse explícitamente.")

if not DATABASE_URL:  # noqa: F405
    raise ImproperlyConfigured("DATABASE_URL es obligatoria en producción (no se permite SQLite).")

if OTP_PROVIDER != "supabase":  # noqa: F405
    raise ImproperlyConfigured(
        'OTP_PROVIDER debe ser "supabase" en producción; el generador local de '
        "códigos está pensado solo para desarrollo y pruebas."
    )

if not (SUPABASE_URL and SUPABASE_ANON_KEY):  # noqa: F405
    raise ImproperlyConfigured(
        "SUPABASE_URL y SUPABASE_ANON_KEY son obligatorias cuando OTP_PROVIDER=supabase."
    )

# ---------------------------------------------------------------------------
# Endurecimiento de transporte y cookies
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405

# ---------------------------------------------------------------------------
# Servicios externos
# ---------------------------------------------------------------------------

if not CACHE_URL:  # noqa: F405
    raise ImproperlyConfigured(
        "CACHE_URL es obligatoria en producción: los límites de intentos deben "
        "compartirse entre todos los workers (por ejemplo redis://localhost:6379/1)."
    )
CACHES = {"default": env.cache_url_config(CACHE_URL)}  # noqa: F405
EMAIL_BACKEND = env("EMAIL_BACKEND")  # noqa: F405

LOGGING["root"]["level"] = env("DJANGO_LOG_LEVEL", default="WARNING")  # noqa: F405

# ---------------------------------------------------------------------------
# Archivos estáticos
# ---------------------------------------------------------------------------

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

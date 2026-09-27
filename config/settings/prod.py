"""
Configuración para producción.

Aplica "fail fast": si falta una variable crítica o una configuración queda en
modo inseguro, el proceso no arranca en lugar de exponer el sistema.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

# ---------------------------------------------------------------------------
# Hosts y orígenes permitidos
#
# A diferencia de desarrollo, aquí no hay valores por defecto: la lista se
# declara explícitamente (denegación por defecto).
# ---------------------------------------------------------------------------

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])  # noqa: F405
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405

# Render publica el hostname del servicio en RENDER_EXTERNAL_HOSTNAME. Se
# agrega automáticamente para que el primer despliegue no falle por un olvido
# de configuración.
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default="")  # noqa: F405
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# ---------------------------------------------------------------------------
# Validaciones de arranque
# ---------------------------------------------------------------------------

if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY es obligatoria en producción.")

if DEBUG:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_DEBUG no puede estar activo en producción.")

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS debe declararse explícitamente. Dentro de Render "
        "basta con no declararla: RENDER_EXTERNAL_HOSTNAME se detecta solo."
    )

if not DATABASE_URL:  # noqa: F405
    raise ImproperlyConfigured("DATABASE_URL es obligatoria en producción (no se permite SQLite).")

if not CACHE_URL:  # noqa: F405
    raise ImproperlyConfigured(
        "CACHE_URL es obligatoria en producción: los límites de intentos de acceso "
        "deben compartirse entre todos los workers. Opciones: dbcache://<tabla> "
        "(requiere 'manage.py createcachetable'), redis://… o memcache://…"
    )

# El proveedor de OTP debe poder entregar el código de verdad.
_BACKENDS_SIN_ENTREGA = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
}

if OTP_PROVIDER == "local":  # noqa: F405
    # El generador local es perfectamente válido en producción: hashea el código
    # con Argon2, lo invalida al primer uso y lo hace expirar. Lo único que exige
    # es un backend de correo que entregue de verdad; con el de consola el código
    # quedaría solo en los logs y nadie podría ingresar con él.
    if EMAIL_BACKEND in _BACKENDS_SIN_ENTREGA:  # noqa: F405
        raise ImproperlyConfigured(
            f"OTP_PROVIDER=local no puede usar '{EMAIL_BACKEND}' en producción: "  # noqa: F405
            "configura un backend SMTP real (EMAIL_BACKEND, EMAIL_HOST, …) "
            "o cambia a OTP_PROVIDER=supabase."
        )
elif OTP_PROVIDER == "supabase":  # noqa: F405
    if not (SUPABASE_URL and SUPABASE_ANON_KEY):  # noqa: F405
        raise ImproperlyConfigured(
            "SUPABASE_URL y SUPABASE_ANON_KEY son obligatorias cuando OTP_PROVIDER=supabase."
        )
else:
    raise ImproperlyConfigured(
        f"OTP_PROVIDER='{OTP_PROVIDER}' no es válido. Usa 'local' o 'supabase'."  # noqa: F405
    )

# ---------------------------------------------------------------------------
# Endurecimiento de transporte y cookies
#
# Render termina el TLS en su balanceador y reenvía por HTTP agregando
# X-Forwarded-Proto. SECURE_PROXY_SSL_HEADER hace que Django reconozca la
# petición como segura, evitando que SECURE_SSL_REDIRECT entre en bucle.
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ---------------------------------------------------------------------------
# Servicios externos
# ---------------------------------------------------------------------------

CACHES = {"default": env.cache_url_config(CACHE_URL)}  # noqa: F405

LOGGING["root"]["level"] = env("DJANGO_LOG_LEVEL", default="WARNING")  # noqa: F405

# ---------------------------------------------------------------------------
# Archivos estáticos
# ---------------------------------------------------------------------------

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

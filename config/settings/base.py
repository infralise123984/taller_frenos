"""
Configuración base compartida por todos los entornos.

Este módulo NO debe contener secretos. Toda credencial se inyecta desde
variables de entorno (archivo .env en desarrollo, variables del sistema en
producción). Ver .env.example para el contrato de configuración.
"""

from pathlib import Path

import environ

# ---------------------------------------------------------------------------
# Rutas y entorno
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env.read_env(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Seguridad y núcleo
# ---------------------------------------------------------------------------

# Sin valor por defecto: cada entorno (dev/prod) decide cómo obtenerla.
# prod.py aborta el arranque si está vacía; dev.py usa una clave local insegura.
SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.humanize",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.workshop",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware
#
# LoginRequiredMiddleware aplica "deny by default": toda vista exige sesión
# autenticada salvo que se marque explícitamente con @login_not_required.
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Base de datos
#
# En desarrollo se usa SQLite; en producción la variable DATABASE_URL
# (postgres://usuario:clave@host:puerto/nombre) tiene precedencia.
# ---------------------------------------------------------------------------

DATABASE_URL = env("DATABASE_URL", default="")

if DATABASE_URL:
    DATABASES = {"default": env.db_url_config(DATABASE_URL)}
    # Reutiliza la conexión entre peticiones en lugar de abrir una nueva en cada
    # una. Los proveedores gestionados (Render incluido) cortan las conexiones
    # ociosas, así que Django comprueba su salud antes de reutilizarlas.
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=600)
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Caché (usado para rate limiting del login)
#
# Sin CACHE_URL se usa memoria del proceso: suficiente en desarrollo, pero no
# válido con varios workers (cada uno tendría su propio contador), por lo que
# producción exige un backend compartido.
# ---------------------------------------------------------------------------

CACHE_URL = env("CACHE_URL", default="")

if CACHE_URL:
    CACHES = {"default": env.cache_url_config(CACHE_URL)}
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "frenos",
        }
    }

# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Argon2 es el hasher recomendado por OWASP. PBKDF2 queda como respaldo para
# verificar hashes heredados de instalaciones previas.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "workshop:buscar"
LOGOUT_REDIRECT_URL = "accounts:login"

# Sesión: jornada laboral del taller. Se renueva con cada request.
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=60 * 60 * 12)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------------------
# Reglas de negocio de autenticación
# ---------------------------------------------------------------------------

# Bloqueo temporal tras intentos fallidos de contraseña.
LOGIN_MAX_FAILED_ATTEMPTS = env.int("LOGIN_MAX_FAILED_ATTEMPTS", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=900)
TOTP_ENCRYPTION_KEY = env("TOTP_ENCRYPTION_KEY", default="")

# Vigencia de los enlaces de invitación. Largo a propósito: nadie revisa el
# correo al instante y volver a invitar es barato.
INVITACION_TTL_DIAS = env.int("INVITACION_TTL_DIAS", default=7)

# Confiar en cabeceras de proxy (X-Forwarded-For) para identificar la IP real.
# Solo activar si el sistema está detrás de un proxy propio; de lo contrario un
# cliente podría falsificar su IP y evadir los límites de intentos.
TRUST_PROXY_HEADERS = env.bool("DJANGO_TRUST_PROXY_HEADERS", default=False)

# ---------------------------------------------------------------------------
# Localización
#
# Django no incluye el locale es_CL: se declara aquí y sus formatos viven en
# config/formats/es_cl/formats.py (puntos para miles, comas para decimales,
# fechas "29 de julio de 2026").
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "es-cl"

# LANGUAGES declara un único idioma a propósito. Con LocaleMiddleware activo,
# un navegador configurado en inglés enviaría Accept-Language: en y las fechas
# y montos se mostrarían en formato inglés. El sistema es monolingüe: si algún
# día se agregan idiomas, basta con ampliar esta lista.
LANGUAGES = [
    ("es-cl", "Español (Chile)"),
]

FORMAT_MODULE_PATH = ["config.formats"]

TIME_ZONE = env("DJANGO_TIME_ZONE", default="America/Santiago")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos y subidos
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Almacenamiento simple en desarrollo. Producción activa la versión comprimida
# con manifiesto, que requiere haber ejecutado collectstatic.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Protección de cabeceras (seguras también en desarrollo)
# ---------------------------------------------------------------------------

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# ---------------------------------------------------------------------------
# Correo (opcional; usado para enviar invitaciones)
# ---------------------------------------------------------------------------

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Taller de Frenos <no-reply@localhost>")

# ---------------------------------------------------------------------------
# Logging estructurado
#
# Los detalles técnicos se registran en el servidor; nunca se exponen al
# usuario final (ver apps.accounts.views).
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("DJANGO_LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

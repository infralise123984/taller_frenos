#!/usr/bin/env bash
#
# Script de build para Render (Build Command: ./build.sh).
# Se ejecuta en cada despliegue, antes de arrancar el servicio.

# Aborta ante cualquier error, incluso dentro de una tubería: es preferible que
# el despliegue falle a que publique un servicio a medio construir.
set -o errexit
set -o pipefail

# manage.py usa config.settings.dev por defecto. Es imprescindible que los pasos
# del build corran con los ajustes de producción: collectstatic debe usar el
# mismo backend de almacenamiento que el servicio en ejecución, o no se generará
# el manifiesto de estáticos (staticfiles.json) que CompressedManifestStaticFilesStorage
# necesita, y la aplicación fallaría al servirlos.
export DJANGO_SETTINGS_MODULE=config.settings.prod

echo "==> Instalando dependencias de producción"
python -m pip install --upgrade pip
python -m pip install -r requirements/prod.txt

# Tailwind se compila aquí y no en el editor, para que el CSS publicado siempre
# corresponda a las clases que usan las plantillas y los módulos de Python. El
# CSS compilado también está versionado, así que si npm no estuviera disponible
# se publica esa versión; el CI ya verificó que esté al día (ver ci.yml).
echo "==> Compilando la hoja de estilos"
if command -v npm >/dev/null 2>&1; then
  npm ci
  npm run build:css
else
  echo "    AVISO: npm no está disponible en este entorno."
  echo "    Se publica static/css/tailwind.css tal como está en el repositorio."
fi

echo "==> Recolectando archivos estáticos"
python manage.py collectstatic --no-input

echo "==> Aplicando migraciones"
python manage.py migrate

# La caché en base de datos necesita su propia tabla. Se crea solo cuando
# CACHE_URL la selecciona: con Redis o Memcached el comando no aplica.
case "${CACHE_URL:-}" in
  dbcache*)
    echo "==> Preparando la tabla de caché"
    python manage.py createcachetable
    ;;
esac

# La primera cuenta administrativa se crea solo si se entregan ambas variables.
# El comando no modifica cuentas existentes ni crea otra si ya hay superusuario.
if [ -n "${BOOTSTRAP_ADMIN_EMAIL:-}" ] || [ -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
  echo "==> Preparando la cuenta administrativa inicial"
  python manage.py bootstrap_admin
fi

echo "==> Build completado"

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

# Datos de ejemplo para mostrar el sistema. Está desactivado por defecto: una
# base de datos con información real no debe recibir registros de fantasía.
# Actívalo solo en un despliegue de demostración, definiendo SEED_DEMO=true.
# El comando es idempotente, así que puede quedar activo entre despliegues.
if [ "${SEED_DEMO:-false}" = "true" ]; then
  echo "==> Cargando datos de demostración"
  python manage.py seed_demo
fi

echo "==> Build completado"

"""Vistas del proyecto expuestas fuera de las aplicaciones de dominio."""

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@login_not_required
@never_cache
@require_GET
def service_worker(request: HttpRequest) -> HttpResponse:
    """Sirve el service worker desde la raíz para permitir el scope de la app."""
    source = (settings.BASE_DIR / "static" / "sw.js").read_text(encoding="utf-8")
    response = HttpResponse(source, content_type="application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    return response

"""Enrutamiento raíz del proyecto."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="workshop:buscar", permanent=False)),
    path("admin/", admin.site.urls),
    path("cuenta/", include("apps.accounts.urls", namespace="accounts")),
    path("taller/", include("apps.workshop.urls", namespace="workshop")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

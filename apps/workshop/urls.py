"""Rutas de la gestión del taller."""

from django.urls import path

from apps.workshop import views

app_name = "workshop"

urlpatterns = [
    path("", views.buscar, name="buscar"),
    path("vehiculo/<str:patente>/", views.vehiculo_detail, name="vehiculo"),
    path("cliente/<int:pk>/", views.cliente_detail, name="cliente"),
    path("ingresos/nuevo/", views.ingreso_create, name="ingreso_create"),
]

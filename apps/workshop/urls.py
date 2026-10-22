"""Rutas de la gestión del taller."""

from django.urls import path

from apps.workshop import views

app_name = "workshop"

urlpatterns = [
    path("", views.buscar, name="buscar"),
    path("vehiculo/<str:patente>/", views.vehiculo_detail, name="vehiculo"),
    path("cliente/<int:pk>/", views.cliente_detail, name="cliente"),
    path("ingresos/nuevo/", views.ingreso_create, name="ingreso_create"),
    path("patentes/estado/", views.patente_estado, name="patente_estado"),
    path("ingresos/<int:pk>/editar/", views.ficha_editar, name="ficha_editar"),
    path("ingresos/<int:pk>/imprimir/", views.ficha_imprimir, name="ficha_imprimir"),
    path("datos-taller/", views.datos_taller, name="datos_taller"),
]

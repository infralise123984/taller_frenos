"""Rutas de la app de cuentas."""

from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("ingresar/", views.login_password, name="login"),
    path("ingresar/codigo/", views.login_otp, name="login_otp"),
    path("salir/", views.logout_view, name="logout"),
    path("invitaciones/", views.invitaciones, name="invitaciones"),
    path("invitaciones/<str:token>/", views.aceptar_invitacion, name="invitacion_aceptar"),
]

"""Rutas de la app de cuentas."""

from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("ingresar/", views.login_password, name="login"),
    path("salir/", views.logout_view, name="logout"),
    path("seguridad/2fa/", views.two_factor_settings, name="two_factor"),
    path("seguridad/2fa/qr/", views.two_factor_qr, name="two_factor_qr"),
    path("invitaciones/", views.invitaciones, name="invitaciones"),
    path("invitaciones/<str:token>/", views.aceptar_invitacion, name="invitacion_aceptar"),
]

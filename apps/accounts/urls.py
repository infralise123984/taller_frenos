"""Rutas de la app de cuentas."""

from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("ingresar/", views.login_password, name="login"),
    path("ingresar/codigo/", views.login_otp, name="login_otp"),
    path("salir/", views.logout_view, name="logout"),
]

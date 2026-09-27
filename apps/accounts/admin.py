"""Registro del panel de administración para cuentas."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import OtpChallenge, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Administración de usuarios del taller basada en correo electrónico."""

    ordering = ("email",)
    list_display = ("email", "full_name", "is_active", "is_staff", "last_otp_login")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    readonly_fields = ("last_login", "date_joined", "last_password_login", "last_otp_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("full_name",)}),
        (
            "Permisos",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (
            "Auditoría",
            {"fields": ("last_login", "last_password_login", "last_otp_login", "date_joined")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2", "is_staff"),
            },
        ),
    )


@admin.register(OtpChallenge)
class OtpChallengeAdmin(admin.ModelAdmin):
    """
    Vista de solo lectura para soporte: permite auditar emisiones de códigos.
    El hash del código se muestra solo para verificar que no se guarda en claro.
    """

    list_display = ("email", "created_at", "expires_at", "attempts", "consumed_at")
    list_filter = ("created_at",)
    search_fields = ("email",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def get_readonly_fields(self, request, obj=None) -> tuple[str, ...]:
        return tuple(field.name for field in self.model._meta.fields)

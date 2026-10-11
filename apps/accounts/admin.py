"""Registro del panel de administración para cuentas."""

import logging

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import Invitacion, User

logger = logging.getLogger(__name__)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Administración de usuarios del taller basada en correo electrónico."""

    ordering = ("email",)
    list_display = (
        "email",
        "full_name",
        "is_active",
        "is_staff",
        "totp_enabled",
        "last_password_login",
    )
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    readonly_fields = ("last_login", "date_joined", "last_password_login")
    actions = ("reset_two_factor",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("full_name",)}),
        (
            "Permisos",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (
            "Auditoría",
            {"fields": ("last_login", "last_password_login", "date_joined")},
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

    @admin.action(description="Restablecer 2FA seleccionado (tras verificar identidad)")
    def reset_two_factor(self, request, queryset) -> None:
        """Permite a administración recuperar acceso tras verificar identidad."""
        users = list(queryset.filter(totp_enabled=True).values_list("pk", "email"))
        if not users:
            self.message_user(request, "Las cuentas seleccionadas no tienen 2FA activo.")
            return

        user_ids = [user_id for user_id, _ in users]
        User.objects.filter(pk__in=user_ids).update(
            totp_enabled=False,
            totp_secret_encrypted="",
            totp_pending_secret_encrypted="",
            totp_pending_expires_at=None,
            totp_last_verified_step=None,
        )
        logger.warning(
            "Administración restableció 2FA tras verificación de identidad; admin=%s usuarios=%s",
            request.user.pk,
            user_ids,
        )
        self.message_user(
            request,
            f"2FA restablecido para {len(users)} cuenta(s). Cada persona deberá "
            "configurarlo nuevamente si lo desea.",
        )


@admin.register(Invitacion)
class InvitacionAdmin(admin.ModelAdmin):
    """
    Solo lectura: las invitaciones se emiten desde la aplicación, donde el
    enlace se entrega una sola vez y no queda almacenado.
    """

    list_display = ("email", "invited_by", "created_at", "expires_at", "estado")
    list_select_related = ("invited_by",)
    list_filter = ("created_at",)
    search_fields = ("email", "invited_by__email")
    date_hierarchy = "created_at"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def get_readonly_fields(self, request, obj=None) -> tuple[str, ...]:
        return tuple(field.name for field in self.model._meta.fields)

    @admin.display(description="estado")
    def estado(self, obj: Invitacion) -> str:
        if obj.accepted_at:
            return "aceptada"
        if obj.revoked_at:
            return "revocada"
        if obj.is_expired:
            return "expirada"
        return "pendiente"

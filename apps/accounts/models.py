"""Modelos de la app de cuentas: usuarios e invitaciones."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

# ---------------------------------------------------------------------------
# Usuario
# ---------------------------------------------------------------------------


class UserManager(BaseUserManager):
    """Manager con el correo electrónico como identificador único."""

    use_in_migrations = True

    def _normalize(self, email: str) -> str:
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        return self.normalize_email(email).lower()

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        """Crea y guarda un usuario activo con la contraseña indicada."""
        email = self._normalize(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean(exclude=["last_login"])
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        """Crea un superusuario con acceso al panel de administración."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superusuario debe tener is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superusuario debe tener is_superuser=True.")

        return self.create_user(email, password, **extra_fields)

    def active(self):
        """Solo cuentas habilitadas."""
        return self.filter(is_active=True)

    def by_email(self, email: str):
        """Búsqueda insensible a mayúsculas por correo."""
        return self.filter(email__iexact=email.strip())


class User(AbstractBaseUser, PermissionsMixin):
    """
    Usuario del taller. El correo electrónico es su identificador único.
    """

    email = models.EmailField("correo electrónico", unique=True)
    full_name = models.CharField("nombre completo", max_length=150, blank=True)
    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField("acceso al panel", default=False)
    date_joined = models.DateTimeField("fecha de alta", default=timezone.now)
    last_password_login = models.DateTimeField(
        "último acceso con contraseña", null=True, blank=True
    )
    totp_enabled = models.BooleanField("autenticación en dos pasos", default=False)
    totp_secret_encrypted = models.TextField("secreto TOTP cifrado", blank=True)
    totp_pending_secret_encrypted = models.TextField("secreto TOTP pendiente cifrado", blank=True)
    totp_pending_expires_at = models.DateTimeField(
        "expira configuración TOTP", null=True, blank=True
    )
    totp_last_verified_step = models.BigIntegerField(
        "último código TOTP usado", null=True, blank=True
    )
    totp_setup_verified_step = models.BigIntegerField(
        "paso TOTP usado al activar", null=True, blank=True
    )
    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["full_name", "email"]

    def __str__(self) -> str:
        return self.full_name or self.email

    def get_full_name(self) -> str:
        return self.full_name or self.email

    def get_short_name(self) -> str:
        return self.full_name.split(" ")[0] if self.full_name else self.email


# ---------------------------------------------------------------------------
# Invitaciones
# ---------------------------------------------------------------------------


class InvitacionQuerySet(models.QuerySet):
    def vigentes(self):
        """Ni usadas, ni revocadas, ni expiradas."""
        return self.filter(
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )

    def for_email(self, email: str):
        return self.filter(email__iexact=email.strip())

    def purge_older_than(self, *, days: int = 30) -> int:
        """Elimina invitaciones antiguas. Pensado para una tarea programada."""
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = self.filter(created_at__lt=cutoff).delete()
        return deleted


class Invitacion(models.Model):
    """
    Permiso para crear una cuenta, emitido por alguien que ya tiene acceso.

    El sistema es de uso interno, así que no existe registro público: la única
    forma de obtener una cuenta es que otra persona autorizada la invite.

    El token viaja en el enlace que se entrega a la persona invitada y **nunca
    se guarda tal cual**, solo su hash SHA-256. A diferencia de un código de seis
    dígitos, aquí el secreto tiene 256 bits de entropía y no es adivinable por
    fuerza bruta, así que un hash rápido es lo adecuado; encarecerlo con Argon2
    solo añadiría latencia sin ganar seguridad.
    """

    email = models.EmailField("correo", db_index=True)
    token_hash = models.CharField("hash del token", max_length=64, unique=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="invitaciones_enviadas",
        verbose_name="invitada por",
    )
    expires_at = models.DateTimeField("expira el")
    accepted_at = models.DateTimeField("aceptada el", null=True, blank=True)
    revoked_at = models.DateTimeField("revocada el", null=True, blank=True)
    created_at = models.DateTimeField("emitida el", auto_now_add=True)

    objects = InvitacionQuerySet.as_manager()

    class Meta:
        verbose_name = "invitación"
        verbose_name_plural = "invitaciones"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "-created_at"], name="invit_email_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Invitación para {self.email}"

    # -- Estado ------------------------------------------------------------

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @property
    def is_usable(self) -> bool:
        return self.accepted_at is None and self.revoked_at is None and not self.is_expired

    # -- Transiciones de estado -------------------------------------------

    def revoke(self) -> None:
        """Anula la invitación. Se usa al emitir una nueva para el mismo correo."""
        now = timezone.now()
        type(self).objects.filter(pk=self.pk).update(revoked_at=now)
        self.revoked_at = now

    def accept(self) -> None:
        now = timezone.now()
        type(self).objects.filter(pk=self.pk).update(accepted_at=now)
        self.accepted_at = now

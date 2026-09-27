"""Modelos de la app de cuentas: usuario propio y desafíos OTP."""

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
    Usuario del taller. Se usa el correo como identificador porque es el mismo
    dato con el que se solicita el código temporal.
    """

    email = models.EmailField("correo electrónico", unique=True)
    full_name = models.CharField("nombre completo", max_length=150, blank=True)
    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField("acceso al panel", default=False)
    date_joined = models.DateTimeField("fecha de alta", default=timezone.now)
    last_password_login = models.DateTimeField(
        "último acceso con contraseña", null=True, blank=True
    )
    last_otp_login = models.DateTimeField("último acceso con código", null=True, blank=True)

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
# Desafíos OTP (usados por el proveedor local)
# ---------------------------------------------------------------------------


class OtpChallengeQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(consumed_at__isnull=True, expires_at__gt=timezone.now())

    def for_email(self, email: str):
        return self.filter(email__iexact=email.strip())


class OtpChallenge(models.Model):
    """
    Código de un solo uso emitido y validado por Django (OTP_PROVIDER=local).

    El código nunca se persiste en texto plano: se guarda únicamente su hash
    calculado con el hasher lento configurado en PASSWORD_HASHERS, de modo que
    un volcado de la base de datos no permita reconstruirlo.
    """

    email = models.EmailField("correo", db_index=True)
    code_hash = models.CharField("hash del código", max_length=255)
    expires_at = models.DateTimeField("expira el")
    attempts = models.PositiveSmallIntegerField("intentos usados", default=0)
    max_attempts = models.PositiveSmallIntegerField("intentos permitidos", default=5)
    consumed_at = models.DateTimeField("consumido el", null=True, blank=True)
    created_at = models.DateTimeField("emitido el", auto_now_add=True)
    request_ip = models.GenericIPAddressField("IP de origen", null=True, blank=True)

    objects = OtpChallengeQuerySet.as_manager()

    class Meta:
        verbose_name = "código de acceso"
        verbose_name_plural = "códigos de acceso"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "-created_at"], name="otp_email_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Código para {self.email} ({self.created_at:%Y-%m-%d %H:%M})"

    # -- Estado ------------------------------------------------------------

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def attempts_exhausted(self) -> bool:
        return self.attempts >= self.max_attempts

    @property
    def is_usable(self) -> bool:
        return not (self.is_consumed or self.is_expired or self.attempts_exhausted)

    # -- Transiciones de estado -------------------------------------------

    def register_failed_attempt(self) -> None:
        """Incrementa el contador de intentos fallidos de forma atómica."""
        type(self).objects.filter(pk=self.pk).update(attempts=models.F("attempts") + 1)
        self.attempts += 1

    def consume(self) -> None:
        """Marca el desafío como usado. Un código válido no puede reutilizarse."""
        now = timezone.now()
        type(self).objects.filter(pk=self.pk).update(consumed_at=now)
        self.consumed_at = now

    # -- Utilidades --------------------------------------------------------

    @classmethod
    def invalidate_pending(cls, email: str) -> int:
        """Invalida los desafíos vigentes del correo antes de emitir uno nuevo."""
        return (
            cls.objects.for_email(email)
            .filter(consumed_at__isnull=True)
            .update(consumed_at=timezone.now())
        )

    @classmethod
    def purge_older_than(cls, *, days: int = 7) -> int:
        """Elimina registros históricos. Pensado para una tarea programada."""
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = cls.objects.filter(created_at__lt=cutoff).delete()
        return deleted

"""
Servicio de invitaciones.

Es la única vía para crear cuentas: el sistema es de uso interno y no tiene
registro público, así que el acceso lo concede alguien que ya está dentro.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.emails import send_invitacion_email
from apps.accounts.exceptions import CorreoYaRegistradoError, InvitacionInvalidaError
from apps.accounts.models import Invitacion, User

logger = logging.getLogger(__name__)

# 32 bytes aleatorios: 256 bits de entropía, imposibles de adivinar.
TOKEN_BYTES = 32

InvitacionSender = Callable[..., None]


@dataclass(frozen=True)
class InvitacionEmitida:
    """Resultado de invitar. El token en claro solo existe aquí y en el correo."""

    invitacion: Invitacion
    enlace: str
    email_enviado: bool


class InvitacionService:
    """Emite y consume invitaciones."""

    def __init__(
        self,
        *,
        invitaciones=Invitacion.objects,
        usuarios=User.objects,
        sender: InvitacionSender = send_invitacion_email,
        ttl_dias: int | None = None,
    ) -> None:
        self._invitaciones = invitaciones
        self._usuarios = usuarios
        self._sender = sender
        self._ttl_dias = settings.INVITACION_TTL_DIAS if ttl_dias is None else ttl_dias

    # -- Emisión -----------------------------------------------------------

    @transaction.atomic
    def invitar(self, *, email: str, invitado_por: User, base_url: str) -> InvitacionEmitida:
        """Crea la invitación y entrega el enlace. Levanta si el correo ya tiene cuenta."""
        normalized = self._normalize(email)

        if self._usuarios.by_email(normalized).exists():
            raise CorreoYaRegistradoError("Ese correo ya tiene una cuenta.")

        token = self._generate_token()

        # Un correo solo debe tener una invitación vigente: al emitir otra, la
        # anterior deja de servir.
        anuladas = (
            self._invitaciones.for_email(normalized).vigentes().update(revoked_at=timezone.now())
        )
        if anuladas:
            logger.info("Se anularon %s invitación(es) previas del mismo correo.", anuladas)

        invitacion = self._invitaciones.create(
            email=normalized,
            token_hash=self._hash(token),
            invited_by=invitado_por,
            expires_at=timezone.now() + timedelta(days=self._ttl_dias),
        )

        enlace = self._build_link(base_url, token)
        enviado = self._send(invitacion, enlace, invitado_por)

        logger.info("Invitación emitida para %s por el usuario %s.", normalized, invitado_por.pk)
        return InvitacionEmitida(invitacion=invitacion, enlace=enlace, email_enviado=enviado)

    # -- Consulta y consumo ------------------------------------------------

    def obtener_utilizable(self, token: str) -> Invitacion:
        """Devuelve la invitación del token, o levanta si ya no sirve."""
        invitacion = self._invitaciones.filter(token_hash=self._hash(token)).first()
        if invitacion is None or not invitacion.is_usable:
            raise InvitacionInvalidaError("El enlace no es válido o ya venció.")
        return invitacion

    @transaction.atomic
    def aceptar(self, *, token: str, password: str) -> User:
        """
        Crea la cuenta y marca la invitación como usada.

        La invitación se bloquea durante la transacción para que dos peticiones
        simultáneas con el mismo enlace no puedan crear dos cuentas.
        """
        invitacion = (
            self._invitaciones.select_for_update().filter(token_hash=self._hash(token)).first()
        )
        if invitacion is None or not invitacion.is_usable:
            raise InvitacionInvalidaError("El enlace no es válido o ya venció.")

        # Alguien pudo crear la cuenta por otra vía entre la invitación y su uso.
        if self._usuarios.by_email(invitacion.email).exists():
            invitacion.revoke()
            raise CorreoYaRegistradoError("Ese correo ya tiene una cuenta.")

        # Las cuentas nuevas entran como usuarias normales: sin acceso al panel
        # de administración, que no necesitan para el trabajo del mesón.
        usuario = self._usuarios.create_user(
            email=invitacion.email,
            password=password,
            full_name="",
        )
        invitacion.accept()

        logger.info("Invitación aceptada: se creó la cuenta %s.", usuario.pk)
        return usuario

    # -- Internos ----------------------------------------------------------

    @staticmethod
    def _normalize(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _generate_token() -> str:
        return secrets.token_urlsafe(TOKEN_BYTES)

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_link(base_url: str, token: str) -> str:
        ruta = reverse("accounts:invitacion_aceptar", args=[token])
        return f"{base_url.rstrip('/')}{ruta}"

    def _send(self, invitacion: Invitacion, enlace: str, invitado_por: User) -> bool:
        """
        Intenta enviar el correo.

        Un fallo de envío no invalida la invitación: el enlace se muestra igual
        en pantalla para poder entregarlo por otra vía, que es lo que hace falta
        en el plan gratuito de Render, donde el SMTP está bloqueado.
        """
        try:
            self._sender(
                email=invitacion.email,
                enlace=enlace,
                invitado_por=invitado_por.get_full_name(),
                ttl_dias=self._ttl_dias,
            )
        except Exception:  # noqa: BLE001 - se degrada a un aviso en pantalla
            logger.exception("No se pudo enviar el correo de invitación.")
            return False
        return True


def build_invitacion_service() -> InvitacionService:
    """Constructor del servicio con sus dependencias por defecto."""
    return InvitacionService()

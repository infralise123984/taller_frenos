"""Composición de correos transaccionales del módulo de cuentas."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail

SUBJECT = "Tu código de acceso al Taller de Frenos"

BODY_TEMPLATE = """Hola,

Tu código temporal para ingresar al sistema del taller es:

    {code}

Es válido por {minutes} minuto(s) y sirve una sola vez.
Si no solicitaste este código, ignora este mensaje: tu contraseña sigue siendo válida.

Taller de Frenos
"""


def send_otp_email(*, email: str, code: str, ttl_seconds: int) -> None:
    """
    Envía el código de un solo uso por correo.

    Se inyecta como dependencia en ``LocalOtpProvider`` para poder sustituirla
    en las pruebas sin tocar el backend de correo.
    """
    minutes = max(1, ttl_seconds // 60)
    send_mail(
        subject=SUBJECT,
        message=BODY_TEMPLATE.format(code=code, minutes=minutes),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )

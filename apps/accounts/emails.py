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


# ---------------------------------------------------------------------------
# Invitaciones
# ---------------------------------------------------------------------------

INVITATION_SUBJECT = "Te dieron acceso al Taller de Frenos"

INVITATION_BODY_TEMPLATE = """Hola,

{invitado_por} te dio acceso al sistema del taller de frenos.

Para crear tu cuenta y elegir tu contraseña, abre este enlace:

    {enlace}

Sirve una sola vez y vence en {dias} día(s).
Si no esperabas esta invitación, ignora este mensaje.

Taller de Frenos
"""


def send_invitacion_email(*, email: str, enlace: str, invitado_por: str, ttl_dias: int) -> None:
    """
    Envía el enlace de invitación.

    Ojo: requiere un backend de correo que entregue de verdad. En el plan
    gratuito de Render el SMTP está bloqueado, así que allí este envío falla y
    el enlace debe entregarse por otra vía; la vista muestra siempre el enlace
    en pantalla justamente para eso.
    """
    send_mail(
        subject=INVITATION_SUBJECT,
        message=INVITATION_BODY_TEMPLATE.format(
            invitado_por=invitado_por or "El taller",
            enlace=enlace,
            dias=ttl_dias,
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )

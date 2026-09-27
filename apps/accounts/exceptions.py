"""
Excepciones de dominio del módulo de autenticación.

Regla de diseño: las vistas capturan estas excepciones y las traducen a
mensajes genéricos. Ningún detalle técnico (proveedor, IP, estado interno)
llega al usuario final.
"""


class AuthenticationDomainError(Exception):
    """Error base de autenticación. Nunca expone su mensaje al cliente."""


# ---------------------------------------------------------------------------
# Acceso por contraseña
# ---------------------------------------------------------------------------


class InvalidCredentialsError(AuthenticationDomainError):
    """Correo o contraseña incorrectos, o la cuenta no existe."""


class AccountInactiveError(AuthenticationDomainError):
    """La cuenta existe pero está deshabilitada."""


class AccountLockedError(AuthenticationDomainError):
    """Se superó el máximo de intentos fallidos y la cuenta está bloqueada temporalmente."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Cuenta bloqueada temporalmente.")
        self.retry_after_seconds = retry_after_seconds


# ---------------------------------------------------------------------------
# Acceso por código de un solo uso (OTP)
# ---------------------------------------------------------------------------


class OtpError(AuthenticationDomainError):
    """Error base del flujo OTP."""


class OtpThrottledError(OtpError):
    """Se solicitó un código demasiadas veces en poco tiempo."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Solicitudes de código demasiado frecuentes.")
        self.retry_after_seconds = retry_after_seconds


class OtpDeliveryError(OtpError):
    """El proveedor de OTP no pudo entregar el código."""


class OtpInvalidError(OtpError):
    """El código ingresado no es válido o ya expiró."""


class OtpVerificationUnavailableError(OtpError):
    """No fue posible verificar el código por un fallo del proveedor."""


# ---------------------------------------------------------------------------
# Invitaciones
# ---------------------------------------------------------------------------


class InvitacionError(AuthenticationDomainError):
    """Error base del flujo de invitaciones."""


class InvitacionInvalidaError(InvitacionError):
    """El enlace no corresponde a ninguna invitación utilizable.

    Cubre todos los casos por igual, a propósito: si el enlace no existe, ya se
    usó, fue anulado o expiró, la persona que lo abre no gana nada sabiendo cuál
    de esas cosas ocurrió.
    """


class CorreoYaRegistradoError(InvitacionError):
    """Ya existe una cuenta con ese correo, así que no hay nada que invitar."""

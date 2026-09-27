"""Puerto de salida para el envío y la validación de códigos de un solo uso."""

from __future__ import annotations

from abc import ABC, abstractmethod


class OtpProvider(ABC):
    """
    Contrato que debe cumplir cualquier proveedor de OTP.

    El resto del sistema depende solo de esta abstracción (Principio de
    Inversión de Dependencias): cambiar de Supabase Auth a otro proveedor
    implica añadir una implementación, sin tocar servicios ni vistas.

    Implementaciones deben:
      * No registrar el código en texto plano.
      * Levantar ``OtpDeliveryError`` si no pueden entregar el código.
      * Levantar ``OtpVerificationUnavailableError`` si el proveedor falla al
        verificar (distinto de "código incorrecto", que se expresa con False).
    """

    @abstractmethod
    def send_code(self, *, email: str, request_ip: str | None = None) -> None:
        """Genera y entrega un código nuevo al correo indicado."""

    @abstractmethod
    def verify_code(self, *, email: str, code: str) -> bool:
        """Devuelve True solo si el código es válido y no ha sido usado."""

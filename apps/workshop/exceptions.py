"""Excepciones de dominio de la gestión del taller."""

from __future__ import annotations


class WorkshopDomainError(Exception):
    """Error base del dominio del taller."""


class PatenteInvalidaError(WorkshopDomainError):
    """La patente no tiene un formato aceptable."""

    def __init__(self, patente: str) -> None:
        super().__init__(f"La patente '{patente}' no es válida.")
        self.patente = patente


class IngresoDuplicadoError(WorkshopDomainError):
    """
    Ya existe una visita con la misma fecha y kilometraje para el vehículo.

    Protege contra el doble envío del formulario de registro rápido.
    """

    def __init__(self, orden_id: int) -> None:
        super().__init__("Ya existe un ingreso con la misma fecha y kilometraje.")
        self.orden_id = orden_id

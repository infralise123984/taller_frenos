"""Excepciones de dominio de la gestión del taller."""

from __future__ import annotations


class WorkshopDomainError(Exception):
    """Error base del dominio del taller."""


class PatenteInvalidaError(WorkshopDomainError):
    """La patente no tiene un formato aceptable."""

    def __init__(self, patente: str) -> None:
        super().__init__(f"La patente '{patente}' no es válida.")
        self.patente = patente


class FichaVaciaError(WorkshopDomainError):
    """La ficha no tiene ninguna línea: no hay nada que cobrar ni que registrar."""

    def __init__(self) -> None:
        super().__init__("La ficha necesita al menos una línea.")


class LineaFichaInvalidaError(WorkshopDomainError):
    """Una línea no cumple las reglas del catálogo de trabajos o del precio."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)


class TotalFichaNegativoError(WorkshopDomainError):
    """El descuento es mayor que el trabajo: el total de la ficha quedaría bajo cero."""

    def __init__(self, total: int) -> None:
        super().__init__("El descuento no puede dejar el total en negativo.")
        self.total = total

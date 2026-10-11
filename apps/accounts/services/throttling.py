"""
Limitadores de tasa apoyados en la caché configurada.

Se implementan como clases pequeñas y cohesivas que solo dependen de la
abstracción de caché de Django, de modo que funcionan igual con LocMemCache,
Memcached o Redis, y pueden aislarse en pruebas inyectando un backend propio.
"""

from __future__ import annotations

import hashlib

from django.core.cache import cache


def _fingerprint(value: str) -> str:
    """Evita escribir correos o IPs en claro dentro de las claves de caché."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:32]


class _CacheBacked:
    """Utilidad común: resolución de claves sobre la caché."""

    def __init__(self, *, namespace: str, cache_backend=None) -> None:
        self._namespace = namespace
        self._cache = cache_backend if cache_backend is not None else cache

    def _key(self, identifier: str) -> str:
        return f"frenos:{self._namespace}:{_fingerprint(identifier)}"

    def _remaining_ttl(self, key: str, *, fallback: int) -> int:
        """
        Segundos restantes de una clave, con respaldo si el backend no soporta ttl().

        LocMemCache no implementa ``ttl()``, así que se devuelve la ventana
        completa: es una estimación conservadora y suficiente para informar al
        usuario cuánto debe esperar.
        """
        ttl_method = getattr(self._cache, "ttl", None)
        if ttl_method is None:
            return fallback

        try:
            ttl = ttl_method(key)
        except NotImplementedError:
            return fallback

        if ttl is None:
            return 0
        return max(0, int(ttl))


class RateLimiter(_CacheBacked):
    """Máximo de N eventos por ventana fija de tiempo."""

    def __init__(
        self,
        *,
        namespace: str,
        max_events: int,
        window_seconds: int,
        cache_backend=None,
    ) -> None:
        super().__init__(namespace=namespace, cache_backend=cache_backend)
        self._max_events = max_events
        self._window_seconds = window_seconds

    def event_count(self, identifier: str) -> int:
        return self._cache.get(self._key(identifier), 0)

    def is_exceeded(self, identifier: str) -> bool:
        return self.event_count(identifier) >= self._max_events

    def register(self, identifier: str) -> int:
        """Suma un evento y devuelve el total acumulado en la ventana actual."""
        key = self._key(identifier)
        # add() solo crea la clave si no existe; así la ventana no se reinicia
        # con cada intento.
        self._cache.add(key, 0, timeout=self._window_seconds)
        try:
            return self._cache.incr(key)
        except ValueError:
            # La clave expiró entre add() e incr(): se abre una ventana nueva.
            self._cache.set(key, 1, timeout=self._window_seconds)
            return 1

    def reset(self, identifier: str) -> None:
        self._cache.delete(self._key(identifier))

    def retry_after_seconds(self, identifier: str) -> int:
        return self._remaining_ttl(self._key(identifier), fallback=self._window_seconds)

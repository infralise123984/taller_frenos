"""Pruebas de los recursos de la interfaz: la hoja de estilos compilada.

La página ya no carga Tailwind desde un CDN, así que estos casos cuidan que el
CSS compilado siga versionado, al día y cargado en el orden correcto.
"""

from __future__ import annotations

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

RUTA_CSS_COMPILADO = "static/css/tailwind.css"


class HojaDeEstilosTests(TestCase):
    def test_la_pantalla_no_depende_de_un_cdn(self) -> None:
        respuesta = self.client.get(reverse("accounts:login"))

        self.assertContains(respuesta, 'href="/static/css/tailwind.css"')
        self.assertContains(respuesta, 'href="/static/css/app.css"')
        self.assertNotContains(respuesta, "cdn.tailwindcss.com")

    def test_el_css_del_sistema_se_carga_despues_de_tailwind(self) -> None:
        """`app.css` debe poder sobrescribir utilidades de Tailwind."""
        contenido = self.client.get(reverse("accounts:login")).content.decode()

        self.assertLess(
            contenido.index("css/tailwind.css"),
            contenido.index("css/app.css"),
        )

    def test_el_css_compilado_incluye_clases_de_plantilla_python_y_javascript(self) -> None:
        """
        Una clase de cada origen declarado en `tailwind.config.js`.

        Si alguna falta, ese origen dejó de escanearse y la interfaz se vería
        distinta sin que nada más falle.
        """
        hoja = (settings.BASE_DIR / RUTA_CSS_COMPILADO).read_text(encoding="utf-8")

        self.assertIn(".hidden{", hoja)  # static/js/ficha.js
        self.assertIn(r"disabled\:opacity-60", hoja)  # apps/ui.py
        self.assertIn(r"sm\:flex-row", hoja)  # templates/partials/_nav.html

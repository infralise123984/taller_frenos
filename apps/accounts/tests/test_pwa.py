"""Pruebas de metadatos y alcance de la aplicación PWA."""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class PwaTests(TestCase):
    def test_base_template_declares_mobile_install_metadata(self) -> None:
        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, 'name="theme-color"')
        self.assertContains(response, 'rel="icon"')
        self.assertContains(response, 'rel="apple-touch-icon"')
        self.assertContains(response, 'src="/static/js/pwa.js"')

    def test_favicon_is_a_valid_multiresolution_ico(self) -> None:
        favicon = settings.BASE_DIR / "static" / "favicon.ico"

        with favicon.open("rb") as icon:
            self.assertEqual(icon.read(4), b"\x00\x00\x01\x00")

    def test_manifest_is_valid_and_scoped_to_the_application(self) -> None:
        manifest_path = settings.BASE_DIR / "static" / "manifest.webmanifest"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(
            {icon["sizes"] for icon in manifest["icons"]},
            {"192x192", "512x512"},
        )

    def test_root_service_worker_is_public_and_can_control_app_scope(self) -> None:
        response = self.client.get(reverse("service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript; charset=utf-8")
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("private", response["Cache-Control"])
        self.assertContains(response, '"/static/css/"')

    def test_service_worker_only_caches_static_paths(self) -> None:
        source = (Path(settings.BASE_DIR) / "static" / "sw.js").read_text(encoding="utf-8")

        self.assertIn('"/static/js/"', source)
        self.assertIn('"/static/icons/"', source)
        self.assertNotIn('request.mode === "navigate"', source)

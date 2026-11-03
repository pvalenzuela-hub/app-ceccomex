import base64
import io
import json
import tempfile
import zipfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import URLResolver, get_resolver, reverse

from comercio.models import ArchivoCarga
from comercio.test_exportaciones import BASE, BULTOS, dus_line
from consultas.models import ConsultaGuardada


PUBLIC_ROUTES = {"health-check", "core-health", "login-check"}
METHODS = ("get", "post", "put", "patch", "delete", "options")


def api_routes(patterns=None):
    """(name, url) of every route under /api/, so a new endpoint is covered without listing it here."""
    if patterns is None:
        patterns = [entry for entry in get_resolver().url_patterns if str(entry.pattern).startswith("api/")]
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from api_routes(entry.url_patterns)
        else:
            kwargs = {key: "json" if key == "format" else "1" for key in entry.pattern.regex.groupindex}
            yield entry.name, reverse(entry.name, kwargs=kwargs)


def upload_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(BASE, dus_line() + "\r\n")
        archive.writestr(BULTOS, "13213653;24022026;1;78;1;\r\n")
    return SimpleUploadedFile("exportaciones-febrero-2026.zip", buffer.getvalue(), content_type="application/zip")


class AnonymousAccessTests(TestCase):
    def test_every_route_but_the_public_ones_rejects_anonymous_requests(self):
        routes = list(api_routes())
        names = {name for name, _ in routes}
        self.assertTrue({"upload-archivo", "system-metrics", "catalogo-codigo-list", "informe-descargar"} <= names)
        self.assertTrue(PUBLIC_ROUTES <= names)
        for name, url in routes:
            if name in PUBLIC_ROUTES:
                continue
            for method in METHODS:
                with self.subTest(route=name, url=url, method=method):
                    self.assertIn(getattr(self.client, method)(url).status_code, (401, 403))

    def test_anonymous_upload_stores_nothing(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media, CELERY_TASK_ALWAYS_EAGER=True):
            response = self.client.post("/api/comercio/upload/", {"archivo": upload_zip(), "tipo_archivo": "EXP_BULTO"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ArchivoCarga.objects.exists())

    def test_basic_credentials_do_not_replace_the_session(self):
        get_user_model().objects.create_user("basic", password="clave-de-prueba")
        header = "Basic " + base64.b64encode(b"basic:clave-de-prueba").decode()
        self.assertEqual(self.client.get("/api/core/metrics/", HTTP_AUTHORIZATION=header).status_code, 403)

    def test_public_routes_stay_open(self):
        for url in ("/api/health/", "/api/core/health/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("csrftoken", response.cookies)
        response = self.client.post("/api/core/login-check/", data=json.dumps({"username": "nadie", "password": "x"}), content_type="application/json")
        self.assertEqual(response.status_code, 400)


class SessionFlowTests(TestCase):
    """The browser sequence: CSRF cookie from health, login, then calls with cookie and X-CSRFToken."""

    def setUp(self):
        get_user_model().objects.create_user("operador", password="clave-de-prueba")
        self.browser = Client(enforce_csrf_checks=True)
        self.browser.get("/api/health/")
        response = self.browser.post(
            "/api/core/login-check/",
            data=json.dumps({"username": "operador", "password": "clave-de-prueba"}),
            content_type="application/json",
            headers={"X-CSRFToken": self.token()},
        )
        self.assertEqual(response.status_code, 200)

    def token(self):
        return self.browser.cookies["csrftoken"].value

    def test_reads_work_with_a_session(self):
        for url in (
            "/api/core/sesion/",
            "/api/core/metrics/",
            "/api/comercio/archivos/",
            "/api/consultas/importaciones/",
            "/api/consultas/pendientes-revision/?limit=20",
            "/api/consultas/favoritos/",
            "/api/catalogos/codigos/",
            "/api/catalogos/partidas/?search=01",
            "/api/reportes/",
            "/api/reportes/importadores/?q=sony",
            "/api/reportes/perfiles-importadores/",
            "/api/reportes/importaciones/partidas/?q=01",
            "/api/reportes/importaciones/configuracion/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.browser.get(url).status_code, 200)

    def test_upload_needs_the_csrf_token_and_works_with_it(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media, CELERY_TASK_ALWAYS_EAGER=True):
            rejected = self.browser.post("/api/comercio/upload/", {"archivo": upload_zip(), "tipo_archivo": "EXP_BULTO"})
            self.assertEqual(rejected.status_code, 403)
            self.assertFalse(ArchivoCarga.objects.exists())
            accepted = self.browser.post("/api/comercio/upload/", {"archivo": upload_zip(), "tipo_archivo": "EXP_BULTO"}, headers={"X-CSRFToken": self.token()})
        self.assertIn(accepted.status_code, (201, 202))
        self.assertEqual(ArchivoCarga.objects.get().estado, "PROCESADO")

    def test_favorite_can_be_saved_and_deleted(self):
        response = self.browser.post(
            "/api/consultas/favoritos/",
            data=json.dumps({"nombre": "Mi consulta", "filtros_json": {}}),
            content_type="application/json",
            headers={"X-CSRFToken": self.token()},
        )
        self.assertEqual(response.status_code, 201)
        deleted = self.browser.delete(f"/api/consultas/favoritos/{response.json()['id']}/", headers={"X-CSRFToken": self.token()})
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(ConsultaGuardada.objects.exists())

    def test_session_stops_working_after_logout(self):
        self.assertEqual(self.browser.post("/api/core/logout/", headers={"X-CSRFToken": self.token()}).status_code, 200)
        self.assertEqual(self.browser.get("/api/core/sesion/").status_code, 403)
        self.assertEqual(self.browser.get("/api/comercio/archivos/").status_code, 403)

    def test_user_administration_stays_restricted_to_superusers(self):
        for url in ("/api/core/usuarios/", "/api/core/usuarios-conectados/"):
            self.assertEqual(self.browser.get(url).status_code, 403)

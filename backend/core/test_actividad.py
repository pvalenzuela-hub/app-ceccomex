import io
import json
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from openpyxl import load_workbook

from core.models import RegistroActividad

PREVIEW = "/api/reportes/importaciones/vista-previa/"
QUERY = {"columnas": ["numero_ident"], "periodo_desde": {"anio": 2026, "mes": 3}, "periodo_hasta": {"anio": 2026, "mes": 3}, "filtros": {"marcas": ["SONY"], "productos": []}}


def acciones():
    return list(RegistroActividad.objects.order_by("id").values_list("usuario_nombre", "accion"))


class RegistroActividadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("sandra", password="clave-segura")
        self.admin = get_user_model().objects.create_superuser("paulo", password="clave-admin")

    def post_json(self, url, body):
        return self.client.post(url, data=json.dumps(body), content_type="application/json")

    def test_logins_logout_and_failed_attempts_are_logged_with_the_typed_name(self):
        self.post_json("/api/core/login-check/", {"username": "sandra", "password": "mala"})
        self.post_json("/api/core/login-check/", {"username": "sandra", "password": "clave-segura"})
        self.client.post("/api/core/logout/")
        self.assertEqual(acciones(), [("sandra", "login_fallido"), ("sandra", "login"), ("sandra", "logout")])
        self.assertIsNone(RegistroActividad.objects.get(accion="login_fallido").usuario)

    def test_query_is_logged_once_and_turning_pages_is_not(self):
        self.client.force_login(self.user)
        self.post_json(PREVIEW, QUERY)
        self.post_json(PREVIEW, {**QUERY, "pagina": 2, "totales": False})
        registro = RegistroActividad.objects.get()
        self.assertEqual((registro.accion, registro.modulo, registro.usuario), ("consulta", "importaciones", self.user))
        self.assertEqual(registro.detalle["filtros"], {"marcas": ["SONY"]})
        self.assertEqual((registro.detalle["registros"], registro.detalle["periodo_desde"]), (0, {"anio": 2026, "mes": 3}))

    def test_upload_rubro_and_catalog_changes_are_logged(self):
        self.client.force_login(self.user)
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            archivo = SimpleUploadedFile("marzo.zip", b"no es zip", content_type="application/zip")
            self.client.post("/api/comercio/upload/", {"archivo": archivo, "tipo_archivo": "IMP"})
        self.post_json("/api/reportes/exportaciones/rubros/", {"nombre": "Cerezas", "configuracion_json": {}})
        self.post_json("/api/catalogos/codigos/", {"grupo": "aduanas", "codigo": "56", "glosa": "ARAUCANIA"})
        carga, rubro, catalogo = RegistroActividad.objects.order_by("id")
        self.assertEqual((carga.accion, carga.detalle["archivo"], carga.detalle["estado"]), ("carga_archivo", "marzo.zip", "ERROR"))
        self.assertEqual((rubro.accion, rubro.modulo, rubro.detalle["rubro"]), ("rubro_creado", "exportaciones", "Cerezas"))
        self.assertEqual((catalogo.accion, catalogo.detalle["registro"]), ("catalogo_creado", "aduanas 56 ARAUCANIA"))

    def test_only_superusers_see_the_log_and_the_summary_counts_each_user(self):
        self.client.force_login(self.user)
        self.post_json(PREVIEW, QUERY)
        self.assertEqual(self.client.get("/api/core/actividad/").status_code, 403)
        self.assertEqual(self.client.get("/api/core/actividad/excel/").status_code, 403)

        self.client.force_login(self.admin)
        data = self.client.get("/api/core/actividad/", {"accion": "consulta", "usuario": "sandra"}).json()
        self.assertEqual((data["count"], data["results"][0]["accion_texto"]), (1, "Consulta"))
        self.assertEqual([(row["usuario_nombre"], row["consultas"]) for row in data["resumen"]], [("sandra", 1)])
        self.assertEqual(self.client.get("/api/core/actividad/", {"accion": "login"}).json()["count"], 0)

        response = self.client.get("/api/core/actividad/excel/")
        sheet = load_workbook(io.BytesIO(b"".join(response.streaming_content))).active
        self.assertEqual([cell.value for cell in sheet[2]][1:4], ["sandra", "Consulta", "importaciones"])

    def test_login_removes_entries_older_than_a_year(self):
        viejo = RegistroActividad.objects.create(usuario_nombre="sandra", accion="consulta")
        RegistroActividad.objects.filter(id=viejo.id).update(fecha=timezone.now() - timedelta(days=400))
        self.post_json("/api/core/login-check/", {"username": "sandra", "password": "clave-segura"})
        self.assertEqual(acciones(), [("sandra", "login")])

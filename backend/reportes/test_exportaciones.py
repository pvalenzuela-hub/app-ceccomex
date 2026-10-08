import io
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from openpyxl import load_workbook

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from comercio.export_loader import export_members, load_member
from comercio.test_exportaciones import BASE, BULTOS, DOCS, dus_line, make_zip


@override_settings(ALLOWED_HOSTS=["testserver"])
class ExportacionesConsultaInformeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        archive = make_zip({
            BASE: [dus_line(), dus_line(item="2", FOBUS="100", CODIGOARANCEL="08061099", NOMBRE="UVAS FRESCAS", ATRIBUTO1="RED GLOBE")],
            BULTOS: ["13213653;24022026;1;22;5;", "13213653;24022026;2;22;7;"],
            DOCS: ["13213653;24022026;1;MAEU1;10012026;POLAR ARGENTINA;266103"],
        })
        for member, tipo in export_members(archive):
            load_member(archive, member, tipo, archivo_path="cargas/x.zip")
        CatalogoCodigo.objects.create(grupo="paises", codigo="218", glosa="ECUADOR")
        CatalogoCodigo.objects.create(grupo="tipos_bulto", codigo="22", glosa="CAJA DE CARTON")
        PartidaArancelaria.objects.create(codigo="08061099", glosa="Las demás uvas frescas")
        cls.user = get_user_model().objects.create_user("analista", password="x")

    def setUp(self):
        self.client.force_login(self.user)

    def test_requires_session(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/consultas/exportaciones/").status_code, 403)
        self.assertEqual(self.client.get("/api/reportes/exportaciones/configuracion/").status_code, 403)

    def test_search_by_tariff_description_with_catalog_glosas(self):
        data = self.client.get("/api/consultas/exportaciones/", {"partida_busqueda": "uvas", "periodo_anio": "2026"}).json()
        self.assertEqual(data["count"], 1)
        row = data["results"][0]
        self.assertEqual((row["item"], row["pais_destino_glosa"], row["partida_glosa"]), ("2", "ECUADOR", "Las demás uvas frescas"))

    def test_dus_detail_includes_bultos_and_documents(self):
        data = self.client.get("/api/consultas/exportaciones/dus/13213653/").json()
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual([bulto["tipo_bulto_glosa"] for bulto in data["bultos"]], ["CAJA DE CARTON", "CAJA DE CARTON"])
        self.assertEqual(data["documentos"][0]["nave"], "POLAR ARGENTINA")

    def test_report_writes_numbers_dus_fields_and_bulto_totals(self):
        config = self.client.get("/api/reportes/exportaciones/configuracion/").json()
        self.assertEqual(config["periodos"], [{"anio": 2026, "mes": 2}])
        response = self.client.post(
            "/api/reportes/exportaciones/exportar/",
            data=json.dumps({
                "periodo_anio": 2026, "periodo_mes": 2, "filtros": {"partidas": ["08061099"]},
                "columnas": ["numero_ident", "pais_destino_glosa", "valor_fob", "dus:ATRIBUTO1", "total_bultos", "tipos_bulto", "naves"],
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        rows = list(load_workbook(io.BytesIO(b"".join(response.streaming_content)), read_only=True).active.iter_rows(values_only=True))
        self.assertEqual(rows[1], ("13213653", "ECUADOR", 100, "RED GLOBE", 12, "CAJA DE CARTON", "POLAR ARGENTINA"))
        self.assertEqual(len(rows), 2)

    def test_report_requires_period(self):
        response = self.client.post("/api/reportes/exportaciones/exportar/", data=json.dumps({"columnas": ["numero_ident"]}), content_type="application/json")
        self.assertEqual(response.status_code, 400)

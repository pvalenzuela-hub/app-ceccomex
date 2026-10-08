from django.test import TestCase, override_settings

from comercio.models import ArchivoCarga, Importacion
from reportes.models import ImportadorProbable
from reportes.views import DIN_LABELS, _filtered_importaciones


def din_row(**positions):
    raw = [""] * len(DIN_LABELS)
    for index, value in positions.items():
        raw[int(index.lstrip("p"))] = value
    return {"raw_columns": raw}


@override_settings(ALLOWED_HOSTS=["testserver"])
class InformeImportacionesUniversoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = ArchivoCarga.objects.create(nombre_archivo="x", archivo="cargas/x.zip", tipo_archivo="IMP")
        cls.sony = ImportadorProbable.objects.create(rut="76123456", dv="0", nombre="SONY CHILE LTDA")
        common = {"archivo_origen": source, "periodo_anio": 2026, "periodo_mes": 2}
        # DIN TXT: brand in DMARCA (134), description split mid-word across DOTRO1/DOTRO2 (136/137).
        cls.tv = Importacion.objects.create(
            **common, numero_ident="1", aduana_codigo="39", pais_origen_codigo="336", importador_probable_sugerido=cls.sony,
            payload_json=din_row(p133="TELEVISOR", p134="SONY-F", p136="PANTALLA LED CON T", p137="ODOS SUS ACCESORIOS", p22="225"),
        )
        # MDB 2015 rows keep named fields instead of DIN positions.
        cls.mango = Importacion.objects.create(
            **common, numero_ident="2", aduana_codigo="14", pais_origen_codigo="219",
            payload_json={"legacy_fields": {"MERCADERIA": "MANGO", "ATRI1": "MACHU PICCHU-F", "PAI_ADQ": "219"}},
        )

    def ids(self, filters):
        return set(_filtered_importaciones(filters, 2026, 2).values_list("numero_ident", flat=True))

    def test_product_terms_search_all_description_fields_and_add_up(self):
        self.assertEqual(self.ids({"productos": ["sony"]}), {"1"})
        self.assertEqual(self.ids({"productos": ["machu picchu"]}), {"2"})
        self.assertEqual(self.ids({"productos": ["sony", "mango"]}), {"1", "2"})
        self.assertEqual(self.ids({"productos": ["todos sus accesorios"]}), {"1"})

    def test_country_of_acquisition_reads_din_position_and_mdb_field(self):
        self.assertEqual(self.ids({"pais_adquisicion_codigo": ["225"]}), {"1"})
        self.assertEqual(self.ids({"pais_adquisicion_codigo": ["219"]}), {"2"})

    def test_importer_origin_country_and_customs_filters(self):
        self.assertEqual(self.ids({"importadores": [str(self.sony.id)]}), {"1"})
        self.assertEqual(self.ids({"pais_origen_codigo": ["219"], "aduana_codigo": ["14"]}), {"2"})
        self.assertEqual(self.ids({"pais_origen_codigo": ["336"], "aduana_codigo": ["14"]}), set())

    def test_importer_search_by_name_rut_and_ids(self):
        by_name = self.client.get("/api/reportes/importadores/", {"q": "sony"}).json()
        by_rut = self.client.get("/api/reportes/importadores/", {"q": "76.123"}).json()
        by_ids = self.client.get("/api/reportes/importadores/", {"ids": str(self.sony.id)}).json()
        self.assertEqual([row["nombre"] for row in by_name + by_rut + by_ids], ["SONY CHILE LTDA"] * 3)

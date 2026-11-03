import io

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from openpyxl import load_workbook

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from comercio.models import ArchivoCarga, Importacion
from reportes.views import DIN_POSITIONS


def din(**values):
    raw = [""] * (max(DIN_POSITIONS.values()) + 1)
    for label, value in values.items():
        raw[DIN_POSITIONS[label]] = value
    return {"raw_columns": raw}


@override_settings(ALLOWED_HOSTS=["testserver"])
class BusquedaDinTests(TestCase):
    """Stored fields hold other data; the screen and its Excel must show the file line."""

    URL = "/api/consultas/importaciones/"

    @classmethod
    def setUpTestData(cls):
        source = ArchivoCarga.objects.create(nombre_archivo="x", archivo="cargas/x.zip", tipo_archivo="IMP")
        common = {"archivo_origen": source, "periodo_anio": 2025, "periodo_mes": 1}
        Importacion.objects.create(
            **common, numero_ident="3693", item="151", fecha_text="23012025", aduana_codigo="13102", pais_origen_codigo="96",
            via_transporte_codigo="32", partida_arancelaria_codigo="00000000", valor_fob="0", valor_cif="200,27",
            payload_json=din(**{"NUMENCRIPTADO": "22079654", "NUMITEM": "2", "FECACEP": "08012025", "ADU": "39", "PA_ORIG": "336", "CODCOMUN": "13102",
                                "VIA_TRAN": "1", "ARANC-NAC": "39199090", "DNOMBRE": "VINILO", "FOB": "800", "FLETE": "150", "SEGURO": "50", "CIF": "1000", "CIF-ITEM": "250"}),
        )
        Importacion.objects.create(
            **common, numero_ident="MDB1", item="1", fecha_text="2015-01-05", aduana_codigo="48", pais_origen_codigo="219", partida_arancelaria_codigo="08045000",
            payload_json={"legacy_fields": {"NUM_IDEN": "MDB1", "NUM_ITEM": "1", "FEC_ACE": "5012015", "COD_ADU": "48", "PAI_ORI": "219", "COD_AAR": "08045000", "MERCADERIA": "MANGO"}},
        )
        for grupo, codigo, glosa in (("aduanas", "39", "SAN ANTONIO"), ("aduanas", "48", "METROPOLITANA"), ("paises", "336", "CHINA"), ("paises", "219", "PERU"), ("comunas", "13102", "CERRILLOS"), ("via_transporte", "1", "MARITIMA")):
            CatalogoCodigo.objects.create(grupo=grupo, codigo=codigo, glosa=glosa)
        PartidaArancelaria.objects.create(codigo="39199090", glosa="Laminas autoadhesivas")
        PartidaArancelaria.objects.create(codigo="08045000", glosa="Mangos")
        cls.user = get_user_model().objects.create_user("analista", password="x")

    def setUp(self):
        cache.clear()
        self.client.force_login(self.user)

    def numeros(self, **params):
        return sorted(row["numero_ident"] for row in self.client.get(self.URL, params).json()["results"])

    def test_row_shows_the_file_line_instead_of_the_stored_fields(self):
        row = next(row for row in self.client.get(self.URL).json()["results"] if row["numero_ident"] == "22079654")
        self.assertEqual((row["item"], row["fecha_text"]), ("2", "08012025"))
        self.assertEqual((row["aduana_codigo"], row["aduana"]["glosa"]), ("39", "SAN ANTONIO"))
        self.assertEqual((row["pais_origen_codigo"], row["pais_origen"]["glosa"]), ("336", "CHINA"))
        self.assertEqual((row["comuna_importador_codigo"], row["comuna_importador"]["glosa"]), ("13102", "CERRILLOS"))
        self.assertEqual((row["partida_arancelaria_codigo"], row["partida"]["glosa"]), ("39199090", "Laminas autoadhesivas"))
        self.assertEqual((row["valor_fob"], row["valor_flete"], row["valor_seguro"], row["valor_cif"]), (200, 37.5, 12.5, 250))

    def test_filters_read_the_file_line(self):
        self.assertEqual(self.numeros(numero_ident="2207"), ["22079654"])
        self.assertEqual(self.numeros(numero_ident="3693"), [])
        self.assertEqual(self.numeros(aduana_codigo="39"), ["22079654"])
        self.assertEqual(self.numeros(aduana_codigo="13102"), [])
        self.assertEqual(self.numeros(pais_origen_codigo="219"), ["MDB1"])
        self.assertEqual(self.numeros(partida_arancelaria_codigo="3919"), ["22079654"])
        self.assertEqual(self.numeros(partida_busqueda="mangos"), ["MDB1"])

    def test_date_filters_compare_the_acceptance_date(self):
        self.assertEqual(self.numeros(fecha_desde="2025-01-01", fecha_hasta="2025-01-31"), ["22079654"])
        self.assertEqual(self.numeros(fecha_hasta="2015-01-05"), ["MDB1"])
        self.assertEqual(self.numeros(fecha_desde="2025-02-01"), [])

    def test_excel_matches_the_screen_filters(self):
        response = self.client.get(f"{self.URL}exportar/", {"partida_busqueda": "laminas"})
        rows = list(load_workbook(io.BytesIO(response.content), read_only=True).active.iter_rows(values_only=True))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][:5], ("22079654", "2", "08012025", "39", "SAN ANTONIO"))
        self.assertEqual(rows[1][12:16], (200, 37.5, 12.5, 250))

    def test_pending_codes_read_the_file_line(self):
        pendientes = self.client.get("/api/consultas/pendientes-revision/").json()["results"]
        self.assertEqual(pendientes, [])
        cache.clear()
        Importacion.objects.create(archivo_origen=ArchivoCarga.objects.first(), periodo_anio=2025, periodo_mes=1, payload_json=din(ADU="77"))
        pendientes = self.client.get("/api/consultas/pendientes-revision/").json()["results"]
        self.assertEqual([(item["campo"], item["codigo"]) for item in pendientes], [("aduana_codigo", "77")])

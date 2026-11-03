import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from openpyxl import load_workbook

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from comercio.busqueda import texto_producto_exportacion, texto_producto_importacion
from comercio.models import ArchivoCarga, Exportacion, ExportacionBulto, Importacion
from reportes.models import ImportadorProbable, RubroImportacion
from reportes.views import DIN_LABELS


IMPORT_URL = "/api/reportes/importaciones/vista-previa/"
EXPORT_URL = "/api/reportes/exportaciones/vista-previa/"
FEBRERO = {"periodo_desde": {"anio": 2026, "mes": 2}, "periodo_hasta": {"anio": 2026, "mes": 2}}


def din_payload(**values):
    raw = [""] * len(DIN_LABELS)
    for label, value in values.items():
        raw[DIN_LABELS.index(label.replace("_", "-"))] = value
    return {"raw_columns": raw}


class VistaPreviaBase(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("analista", password="x"))

    def post(self, url, **body):
        return self.client.post(url, data=json.dumps({"columnas": ["numero_ident"], **FEBRERO, **body}), content_type="application/json")


@override_settings(ALLOWED_HOSTS=["testserver"])
class VistaPreviaImportacionesTests(VistaPreviaBase):
    @classmethod
    def setUpTestData(cls):
        source = ArchivoCarga.objects.create(nombre_archivo="x", archivo="cargas/x.zip", tipo_archivo="IMP")
        common = {"archivo_origen": source, "periodo_anio": 2026, "periodo_mes": 2}
        din = {"CIF": "1000", "FOB": "800"}
        rows = [
            # One DIN with three items: "CIF" and "FOB" repeat on each of them.
            {"numero_ident": "A", "aduana_codigo": "39", "payload_json": din_payload(**din, CIF_ITEM="250", CANT_MERC="10", MEDIDA="6", DNOMBRE="TELEVISOR")},
            {"numero_ident": "A", "aduana_codigo": "39", "payload_json": din_payload(**din, CIF_ITEM="250,5", CANT_MERC=",5", MEDIDA="6", DNOMBRE="RADIO")},
            {"numero_ident": "A", "aduana_codigo": "39", "payload_json": din_payload(**din, CIF_ITEM="499,5", CANT_MERC="3", MEDIDA="10", DNOMBRE="NEUMATICO")},
            # MDB 2015 layout: named fields and a decimal point.
            {"numero_ident": "B", "aduana_codigo": "14", "payload_json": {"legacy_fields": {"CIF_TOTAL": "12000.00", "VAL_FOB": "10000", "CIF_ITEM": "12000.00", "CANT_MERC": "6000", "COD_UMED": "6", "MERCADERIA": "MANGO"}}},
            # Text in an amount field must not break the sum for everyone else.
            {"numero_ident": "C", "aduana_codigo": "14", "payload_json": din_payload(CIF="SIN DATO", FOB="", CIF_ITEM="N/D", CANT_MERC="", MEDIDA="", DNOMBRE="DATO MALO")},
        ]
        for row in rows:
            Importacion.objects.create(**common, **row, texto_producto=texto_producto_importacion(row["payload_json"]))
        Importacion.objects.create(archivo_origen=source, periodo_anio=2026, periodo_mes=3, numero_ident="OTRO_MES", payload_json=din_payload(**din, CIF_ITEM="1000"))
        CatalogoCodigo.objects.create(grupo="unidades_medida", codigo="6", glosa="KILOS NETOS")

    def test_document_with_several_items_does_not_repeat_its_amounts(self):
        data = self.post(IMPORT_URL).json()
        totales = data["totales"]
        self.assertEqual(data["registros"], 5)
        self.assertEqual(totales["documentos"], 3)
        # Summing the repeated "CIF" per item would give 3000 + 12000 for these two DIN.
        self.assertEqual(totales["cif_usd"], 13000)
        self.assertEqual(totales["fob_usd"], 10800)

    def test_filtered_items_only_count_their_share_of_the_document(self):
        totales = self.post(IMPORT_URL, filtros={"productos": ["televisor"]}).json()["totales"]
        self.assertEqual((totales["cif_usd"], totales["fob_usd"], totales["documentos"]), (250, 200, 1))

    def test_quantities_are_reported_per_unit_and_accept_leading_comma(self):
        totales = self.post(IMPORT_URL).json()["totales"]
        self.assertEqual(totales["cantidad"], 6013.5)
        self.assertEqual(
            totales["cantidades_por_unidad"],
            [{"unidad": "6", "glosa": "KILOS NETOS", "cantidad": 6010.5}, {"unidad": "10", "glosa": "", "cantidad": 3}],
        )

    def test_empty_result_has_zero_totals(self):
        data = self.post(IMPORT_URL, filtros={"marcas": ["no existe"]}).json()
        self.assertEqual((data["registros"], data["filas"]), (0, []))
        self.assertEqual((data["totales"]["cif_usd"], data["totales"]["cantidades_por_unidad"]), (0, []))

    def test_pages_keep_every_row_once_and_can_skip_the_totals(self):
        first = self.post(IMPORT_URL, por_pagina=2).json()
        second = self.post(IMPORT_URL, por_pagina=2, pagina=2, totales=False).json()
        last = self.post(IMPORT_URL, por_pagina=2, pagina=3, totales=False).json()
        self.assertEqual((first["pagina"], first["paginas"], first["registros"]), (1, 3, 5))
        self.assertIsNone(second["totales"])
        rows = first["filas"] + second["filas"] + last["filas"]
        self.assertEqual(sorted(row[0] for row in rows), ["A", "A", "A", "B", "C"])

    def test_rows_use_the_same_column_values_as_the_excel(self):
        data = self.post(IMPORT_URL, columnas=["numero_ident", "raw:158", "valor_fob"], filtros={"productos": ["televisor"]}).json()
        self.assertEqual([column["label"] for column in data["columnas"]], ["Nº identificador", "CIF Item", "VAL-FOB-ITEM - FOB-Item"])
        self.assertEqual(data["filas"], [["A", 250, 200]])

    def test_saved_rubro_with_filters_out_of_the_universe_keeps_filtering(self):
        rubro = RubroImportacion.objects.create(tipo="IMP", nombre="Antiguo", configuracion_json={"columnas": ["numero_ident"], "filtros": {"aduana_codigo": ["14"]}})
        data = self.post(IMPORT_URL, filtros=rubro.configuracion_json["filtros"]).json()
        self.assertEqual(sorted(row[0] for row in data["filas"]), ["B", "C"])

    def test_brand_and_product_must_both_match(self):
        self.assertEqual(self.post(IMPORT_URL, filtros={"marcas": ["televisor"], "productos": ["radio"]}).json()["registros"], 0)
        self.assertEqual(self.post(IMPORT_URL, filtros={"marcas": ["televisor"], "productos": ["tele"]}).json()["registros"], 1)

    def test_totals_are_skipped_above_the_row_limit(self):
        with patch("reportes.views.PREVIEW_MAX_TOTAL_ROWS", 4):
            data = self.post(IMPORT_URL).json()
        self.assertIsNone(data["totales"])
        self.assertTrue(data["totales_omitidos"])
        self.assertEqual(data["registros"], 5)

    def test_rejects_invalid_requests(self):
        inverted = {"periodo_desde": {"anio": 2026, "mes": 3}, "periodo_hasta": {"anio": 2026, "mes": 1}}
        self.assertEqual(self.post(IMPORT_URL, **inverted).status_code, 400)
        self.assertEqual(self.post(IMPORT_URL, columnas=["no_existe"]).status_code, 400)
        self.assertEqual(self.post(IMPORT_URL, filtros=["no es objeto"]).status_code, 400)

    def test_requires_session(self):
        self.client.logout()
        self.assertEqual(self.post(IMPORT_URL).status_code, 403)
        self.assertEqual(self.post(EXPORT_URL).status_code, 403)


@override_settings(ALLOWED_HOSTS=["testserver"])
class VistaPreviaExportacionesTests(VistaPreviaBase):
    @classmethod
    def setUpTestData(cls):
        source = ArchivoCarga.objects.create(nombre_archivo="x", archivo="cargas/x.zip", tipo_archivo="EXP")
        common = {"archivo_origen": source, "periodo_anio": 2026, "periodo_mes": 2, "unidad_medida_codigo": "6"}
        dus = {"numero_ident": "D1", "valor_fob_dus": "400.00", "valor_flete_dus": "30", "valor_cif_dus": "440.00"}
        rows = [
            {**dus, "item": "1", "valor_fob": "100.00", "cantidad_mercancia": "10", "payload_json": {"dus_fields": {"NOMBRE": "UVAS"}}},
            {**dus, "item": "2", "valor_fob": "300.00", "cantidad_mercancia": "20.5", "payload_json": {"dus_fields": {"NOMBRE": "CEREZAS"}}},
            # Most DUS declare no CIF.
            {"numero_ident": "D2", "item": "1", "valor_fob_dus": "50", "valor_cif_dus": "0", "valor_fob": "50", "cantidad_mercancia": "1", "payload_json": {"dus_fields": {"NOMBRE": "UVAS"}}},
        ]
        for row in rows:
            Exportacion.objects.create(**common, **row, texto_producto=texto_producto_exportacion(row["payload_json"]))
        ExportacionBulto.objects.create(archivo_origen=source, periodo_anio=2026, periodo_mes=2, numero_ident="D1", secuencia=1, cantidad_bultos="7", tipo_bulto_codigo="22")

    def test_document_with_several_items_does_not_repeat_its_amounts(self):
        data = self.post(EXPORT_URL).json()
        totales = data["totales"]
        self.assertEqual(data["registros"], 3)
        # Summing the repeated CIF per item would give 880 for D1, and the repeated FOB 800 + 50.
        self.assertEqual((totales["cif_usd"], totales["fob_usd"]), (440, 450))
        self.assertEqual((totales["documentos"], totales["documentos_con_cif"]), (2, 1))
        self.assertEqual(totales["cantidad"], 31.5)

    def test_filtered_items_only_count_their_share_of_the_document(self):
        totales = self.post(EXPORT_URL, filtros={"productos": ["cerezas"]}).json()["totales"]
        self.assertEqual((totales["cif_usd"], totales["fob_usd"], totales["documentos"]), (330, 300, 1))

    def test_rows_read_bultos_of_the_page(self):
        data = self.post(EXPORT_URL, columnas=["numero_ident", "total_bultos"], por_pagina=1).json()
        self.assertEqual(data["filas"], [["D1", 7]])


@override_settings(ALLOWED_HOSTS=["testserver"], CELERY_TASK_ALWAYS_EAGER=True)
class FiltrosColumnaImportacionesTests(VistaPreviaBase):
    @classmethod
    def setUpTestData(cls):
        source = ArchivoCarga.objects.create(nombre_archivo="x", archivo="cargas/x.zip", tipo_archivo="IMP")
        common = {"archivo_origen": source, "periodo_anio": 2026, "periodo_mes": 2}
        din = {"CIF": "1000", "FOB": "800", "MEDIDA": "6"}
        sony = ImportadorProbable.objects.create(rut="76123456", dv="0", nombre="SONY CHILE LTDA")
        rows = [
            {"numero_ident": "A", "aduana_codigo": "39", "partida_arancelaria_codigo": "85287200", "importador_probable_sugerido": sony,
             "payload_json": din_payload(**din, CIF_ITEM="250,5", CANT_MERC=",07", DNOMBRE="TELEVISOR", DMARCA="SONY-F", DVARIEDAD="OLED")},
            {"numero_ident": "A", "aduana_codigo": "39", "partida_arancelaria_codigo": "85171300", "importador_probable_sugerido": sony,
             "payload_json": din_payload(**din, CIF_ITEM="749,5", CANT_MERC="3", DNOMBRE="TELEFONO", DMARCA="SONYERICSSON-F")},
            {"numero_ident": "B", "aduana_codigo": "14", "partida_arancelaria_codigo": "08045000",
             "payload_json": {"legacy_fields": {"CIF_TOTAL": "500", "VAL_FOB": "400", "CIF_ITEM": "500", "CANT_MERC": "10", "COD_UMED": "6", "MERCADERIA": "MANGO", "ATRI1": "MACHU PICCHU-F", "IMPORT": "FRUTERA LTDA", "RUT": "77000111"}}},
        ]
        for row in rows:
            Importacion.objects.create(**common, **row, texto_producto=texto_producto_importacion(row["payload_json"]))
        CatalogoCodigo.objects.create(grupo="aduanas", codigo="39", glosa="METROPOLITANA")
        CatalogoCodigo.objects.create(grupo="aduanas", codigo="14", glosa="SAN ANTONIO")
        PartidaArancelaria.objects.create(codigo="85287200", glosa="Televisores en colores")
        PartidaArancelaria.objects.create(codigo="08045000", glosa="Mangos y mangostanes")

    def idents(self, **filtros):
        response = self.post(IMPORT_URL, filtros_columnas=filtros)
        self.assertEqual(response.status_code, 200, response.content)
        return sorted(row[0] for row in response.json()["filas"])

    def test_filters_text_catalog_and_period_columns(self):
        self.assertEqual(self.idents(numero_ident="b"), ["B"])
        self.assertEqual(self.idents(aduana_glosa="metropol"), ["A", "A"])
        self.assertEqual(self.idents(partida_glosa="mangostanes"), ["B"])
        self.assertEqual(self.idents(partida_arancelaria_codigo="8528"), ["A"])
        self.assertEqual(self.idents(importador_probable="frutera"), ["B"])
        self.assertEqual(self.idents(importador_probable="sony"), ["A", "A"])
        self.assertEqual(self.idents(importador_rut="77000"), ["B"])
        self.assertEqual(self.idents(periodo_mes="2"), ["A", "A", "B"])
        self.assertEqual(self.idents(periodo_mes="12"), [])

    def test_filters_amount_columns_with_comma_or_point(self):
        cif_item = f"raw:{DIN_LABELS.index('CIF-ITEM')}"
        cantidad = f"raw:{DIN_LABELS.index('CANT-MERC')}"
        self.assertEqual(self.idents(**{cif_item: "250,5"}), ["A"])
        self.assertEqual(self.idents(**{cif_item: "250.5"}), ["A"])
        self.assertEqual(self.idents(**{cantidad: "0,07"}), ["A"])

    def test_filters_computed_columns_by_what_the_table_shows(self):
        marca = f"raw:{DIN_LABELS.index('DMARCA')}"
        nombre = f"raw:{DIN_LABELS.index('DNOMBRE')}"
        self.assertEqual(self.idents(**{marca: "machu picchu"}), ["B"])
        # "-F" closes the brand in the file but is not part of it.
        self.assertEqual(self.idents(**{marca: "sony-f"}), [])
        self.assertEqual(self.idents(**{marca: "sony"}), ["A", "A"])
        # OLED is in the product text but in another column.
        self.assertEqual(self.idents(**{nombre: "oled"}), [])
        self.assertEqual(self.idents(valor_fob="200,4"), ["A"])

    def test_columns_combine_and_totals_follow_the_filters(self):
        marca = f"raw:{DIN_LABELS.index('DMARCA')}"
        nombre = f"raw:{DIN_LABELS.index('DNOMBRE')}"
        data = self.post(IMPORT_URL, filtros_columnas={marca: "sony", nombre: "televisor", "aduana_glosa": "metro"}).json()
        self.assertEqual(data["registros"], 1)
        self.assertEqual((data["totales"]["cif_usd"], data["totales"]["fob_usd"], data["totales"]["documentos"]), (250.5, 200.4, 1))

    def test_unknown_columns_and_blank_text_are_ignored(self):
        self.assertEqual(self.idents(no_existe="x", numero_ident="  "), ["A", "A", "B"])

    def test_too_many_rows_for_a_computed_column_asks_to_narrow_the_search(self):
        with patch("reportes.views.COLUMNA_MAX_FILAS_CALCULADAS", 1):
            response = self.post(IMPORT_URL, filtros_columnas={"iva_item": "1"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Acote", response.json()["detail"])

    def test_excel_has_the_rows_filtered_on_screen(self):
        with tempfile.TemporaryDirectory() as folder, patch("reportes.tasks.INFORMES_DIR", Path(folder)):
            informe = self.post("/api/reportes/importaciones/exportar/", filtros_columnas={"aduana_glosa": "san antonio"}).json()
            self.assertEqual((informe["estado"], informe["filas_total"]), ("LISTO", 1))
            download = self.client.get(f"/api/reportes/informes/{informe['id']}/descargar/")
            rows = list(load_workbook(io.BytesIO(b"".join(download.streaming_content)), read_only=True).active.iter_rows(values_only=True))
        self.assertEqual(rows[1:], [("B",)])

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalogos.models import CatalogoCodigo
from comercio.busqueda import texto_producto_exportacion, texto_producto_importacion
from comercio.models import ArchivoCarga, Exportacion, ExportacionBulto, Importacion
from reportes.models import RubroImportacion
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

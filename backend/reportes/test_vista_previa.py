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
from comercio.models import ArchivoCarga, Exportacion, ExportacionBulto, ExportacionDocTransporte, Importacion
from reportes.models import ImportadorProbable, RubroImportacion
from reportes.views import DIN_LABELS


IMPORT_URL = "/api/reportes/importaciones/vista-previa/"
EXPORT_URL = "/api/reportes/exportaciones/vista-previa/"
FEBRERO = {"periodo_desde": {"anio": 2026, "mes": 2}, "periodo_hasta": {"anio": 2026, "mes": 2}}


def din_payload(**values):
    raw = [""] * len(DIN_LABELS)
    for label, value in values.items():
        # CIF_ITEM stands for CIF-ITEM; PA_ORIG is the real name.
        raw[DIN_LABELS.index(label if label in DIN_LABELS else label.replace("_", "-"))] = value
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
        self.assertEqual(self.idents(importador_rut="76123456"), ["A", "A"])
        self.assertEqual(self.idents(importador_dv="0"), ["A", "A"])
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
        with patch("reportes.columnas.COLUMNA_MAX_FILAS_CALCULADAS", 1):
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


@override_settings(ALLOWED_HOSTS=["testserver"])
class CodigosDinCorridosTests(VistaPreviaBase):
    """Rows loaded before the parser followed the DIN positions: 13102 is a comuna, 96 a via."""

    @classmethod
    def setUpTestData(cls):
        source = ArchivoCarga.objects.create(nombre_archivo="x", archivo="cargas/x.zip", tipo_archivo="IMP")
        common = {"archivo_origen": source, "periodo_anio": 2026, "periodo_mes": 2}
        Importacion.objects.create(**common, numero_ident="VIEJA", aduana_codigo="13102", pais_origen_codigo="96", partida_arancelaria_codigo="00000000", comuna_importador_codigo="", payload_json=din_payload(ADU="39", PA_ORIG="336", CODCOMUN="13102", ARANC_NAC="39199090", ARANC_ALA="00000000"))
        Importacion.objects.create(**common, numero_ident="MDB", aduana_codigo="", pais_origen_codigo="", partida_arancelaria_codigo="08045000", payload_json={"legacy_fields": {"COD_ADU": "48", "PAI_ORI": "219", "COD_AAR": "08045000"}})
        CatalogoCodigo.objects.create(grupo="aduanas", codigo="39", glosa="SAN ANTONIO")
        CatalogoCodigo.objects.create(grupo="aduanas", codigo="48", glosa="METROPOLITANA")
        CatalogoCodigo.objects.create(grupo="paises", codigo="336", glosa="CHINA")
        CatalogoCodigo.objects.create(grupo="paises", codigo="219", glosa="PERU")
        CatalogoCodigo.objects.create(grupo="comunas", codigo="13102", glosa="CERRILLOS")
        PartidaArancelaria.objects.create(codigo="39199090", glosa="Las demás láminas autoadhesivas")
        PartidaArancelaria.objects.create(codigo="08045000", glosa="Mangos")

    def test_columns_show_the_code_of_the_file_line(self):
        columnas = ["numero_ident", "aduana_codigo", "aduana_glosa", "pais_origen_codigo", "pais_origen_glosa"]
        filas = {fila[0]: fila[1:] for fila in self.post(IMPORT_URL, columnas=columnas).json()["filas"]}
        self.assertEqual(filas["VIEJA"], ["39", "SAN ANTONIO", "336", "CHINA"])
        self.assertEqual(filas["MDB"], ["48", "METROPOLITANA", "219", "PERU"])

    def test_filters_of_saved_rubros_and_columns_use_the_same_code(self):
        def idents(**body):
            return sorted(fila[0] for fila in self.post(IMPORT_URL, **body).json()["filas"])

        self.assertEqual(idents(filtros={"aduana_codigo": ["39"]}), ["VIEJA"])
        self.assertEqual(idents(filtros={"pais_origen_codigo": ["219"]}), ["MDB"])
        self.assertEqual(idents(filtros={"aduana_codigo": ["13102"]}), [])
        self.assertEqual(idents(filtros_columnas={"aduana_glosa": "san antonio"}), ["VIEJA"])
        self.assertEqual(idents(filtros_columnas={"pais_origen_glosa": "peru"}), ["MDB"])
        self.assertEqual(idents(filtros_columnas={"pais_origen_codigo": "336"}), ["VIEJA"])

    def test_tariff_and_comuna_come_from_the_file_line(self):
        columnas = ["numero_ident", "partida_arancelaria_codigo", "partida_glosa", "comuna_importador_codigo", "comuna_importador_glosa"]
        filas = {fila[0]: fila[1:] for fila in self.post(IMPORT_URL, columnas=columnas).json()["filas"]}
        self.assertEqual(filas["VIEJA"], ["39199090", "Las demás láminas autoadhesivas", "13102", "CERRILLOS"])
        self.assertEqual(filas["MDB"], ["08045000", "Mangos", "", ""])

    def test_tariff_and_comuna_filters_use_the_file_line(self):
        def idents(**body):
            return sorted(fila[0] for fila in self.post(IMPORT_URL, **body).json()["filas"])

        self.assertEqual(idents(filtros={"partidas": ["39199090"]}), ["VIEJA"])
        self.assertEqual(idents(filtros={"partidas": ["00000000"]}), [])
        self.assertEqual(idents(filtros={"comuna_importador_codigo": ["13102"]}), ["VIEJA"])
        self.assertEqual(idents(filtros_columnas={"partida_arancelaria_codigo": "3919"}), ["VIEJA"])
        self.assertEqual(idents(filtros_columnas={"partida_glosa": "laminas"}), ["VIEJA"])
        self.assertEqual(idents(filtros_columnas={"comuna_importador_glosa": "cerrillos"}), ["VIEJA"])

    def test_documents_are_din_numbers_not_importers(self):
        common = {"archivo_origen": ArchivoCarga.objects.first(), "periodo_anio": 2026, "periodo_mes": 3}
        # The current loader stores the importer number in numero_ident: two DIN of the same importer.
        for din in ("D1", "D1", "D2"):
            Importacion.objects.create(**common, numero_ident="3693", payload_json=din_payload(NUMENCRIPTADO=din))
        marzo = {"periodo_desde": {"anio": 2026, "mes": 3}, "periodo_hasta": {"anio": 2026, "mes": 3}}
        data = self.post(IMPORT_URL, **marzo).json()
        self.assertEqual(data["totales"]["documentos"], 2)
        self.assertEqual(sorted(fila[0] for fila in data["filas"]), ["D1", "D1", "D2"])


IMPORT_VALORES = IMPORT_URL + "valores/"
EXPORT_VALORES = EXPORT_URL + "valores/"


def excel_rows(test, url, **body):
    with tempfile.TemporaryDirectory() as folder, patch("reportes.tasks.INFORMES_DIR", Path(folder)):
        informe = test.post(url, **body).json()
        test.assertEqual(informe["estado"], "LISTO", informe)
        download = test.client.get(f"/api/reportes/informes/{informe['id']}/descargar/")
        return list(load_workbook(io.BytesIO(b"".join(download.streaming_content)), read_only=True).active.iter_rows(values_only=True))[1:]


@override_settings(ALLOWED_HOSTS=["testserver"], CELERY_TASK_ALWAYS_EAGER=True)
class ListasColumnaImportacionesTests(VistaPreviaBase):
    MARCA = f"raw:{DIN_LABELS.index('DMARCA')}"
    NOMBRE = f"raw:{DIN_LABELS.index('DNOMBRE')}"

    @classmethod
    def setUpTestData(cls):
        source = ArchivoCarga.objects.create(nombre_archivo="x", archivo="cargas/x.zip", tipo_archivo="IMP")
        common = {"archivo_origen": source, "periodo_anio": 2026, "periodo_mes": 2}
        din = {"CIF": "1000", "FOB": "800", "CIF_ITEM": "500", "MEDIDA": "6"}
        for numero, aduana, nombre, marca in (("A", "39", "TELEVISOR", "SONY-F"), ("B", "39", "RADIO", "SONY-F"), ("C", "48", "TELEVISOR", "LG-F")):
            payload = din_payload(**din, NUMENCRIPTADO=numero, ADU=aduana, DNOMBRE=nombre, DMARCA=marca)
            Importacion.objects.create(**common, numero_ident=numero, payload_json=payload, texto_producto=texto_producto_importacion(payload))
        Importacion.objects.create(archivo_origen=source, periodo_anio=2026, periodo_mes=3, numero_ident="MARZO", payload_json=din_payload(ADU="55", DNOMBRE="OTRO MES", DMARCA="MARZO-F"))
        CatalogoCodigo.objects.create(grupo="aduanas", codigo="39", glosa="SAN ANTONIO")
        CatalogoCodigo.objects.create(grupo="aduanas", codigo="48", glosa="METROPOLITANA")
        CatalogoCodigo.objects.create(grupo="aduanas", codigo="55", glosa="TALCAHUANO")

    def valores(self, columna, **body):
        response = self.post(IMPORT_VALORES, columna=columna, **body)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_lists_come_from_the_period_and_the_other_filters(self):
        self.assertEqual(self.valores("aduana_glosa")["valores"], ["METROPOLITANA", "SAN ANTONIO"])
        self.assertEqual(self.valores(self.MARCA)["valores"], ["LG", "SONY"])
        self.assertEqual(self.valores("numero_ident")["valores"], ["A", "B", "C"])
        self.assertEqual(self.valores("aduana_glosa", filtros_columnas={self.MARCA: ["LG"]})["valores"], ["METROPOLITANA"])
        self.assertEqual(self.valores(self.MARCA, filtros={"productos": ["radio"]})["valores"], ["SONY"])

    def test_a_list_ignores_its_own_filter_so_other_values_can_be_added(self):
        self.assertEqual(self.valores("aduana_glosa", filtros_columnas={"aduana_glosa": ["METROPOLITANA"]})["valores"], ["METROPOLITANA", "SAN ANTONIO"])

    def test_lists_can_be_searched_and_warn_when_cut(self):
        self.assertEqual(self.valores("aduana_glosa", buscar="metro")["valores"], ["METROPOLITANA"])
        self.assertEqual(self.valores(self.MARCA, buscar="son")["valores"], ["SONY"])
        cut = self.valores("numero_ident", limite=2)
        self.assertEqual((cut["valores"], cut["recortada"]), (["A", "B"], True))
        self.assertFalse(self.valores("numero_ident", limite=3)["recortada"])
        self.assertTrue(self.valores("aduana_glosa", limite=1)["recortada"])

    def test_computed_list_asks_to_search_when_there_are_too_many_rows(self):
        with patch("reportes.columnas.COLUMNA_MAX_FILAS_CALCULADAS", 2):
            self.assertTrue(self.valores(self.MARCA)["requiere_busqueda"])
            found = self.valores(self.MARCA, buscar="LG")
        self.assertEqual((found["valores"], found["requiere_busqueda"]), (["LG"], False))

    def test_numeric_and_date_columns_have_no_list(self):
        columnas = [self.MARCA, "aduana_glosa", "numero_ident", f"raw:{DIN_LABELS.index('CIF-ITEM')}", f"raw:{DIN_LABELS.index('FECACEP')}", "valor_fob", "periodo_mes"]
        tipos = {column["key"]: column["filtro"] for column in self.post(IMPORT_URL, columnas=columnas).json()["columnas"]}
        self.assertEqual([tipos[key] for key in columnas], ["lista", "lista", "lista", "texto", "texto", "texto", "texto"])
        self.assertEqual(self.post(IMPORT_VALORES, columna="valor_fob").status_code, 400)
        self.assertEqual(self.post(IMPORT_VALORES, columna="no_existe").status_code, 400)

    def test_selected_values_match_exactly_on_screen_totals_and_excel(self):
        filtros = {"aduana_glosa": ["SAN ANTONIO"], self.MARCA: ["SONY"], self.NOMBRE: ["RADIO", "TELEVISOR"]}
        data = self.post(IMPORT_URL, filtros_columnas=filtros).json()
        self.assertEqual(sorted(fila[0] for fila in data["filas"]), ["A", "B"])
        self.assertEqual(data["totales"]["cif_usd"], 1000)
        self.assertEqual(sorted(row[0] for row in excel_rows(self, "/api/reportes/importaciones/exportar/", filtros_columnas=filtros)), ["A", "B"])
        # A selected value is the whole cell, not a fragment.
        self.assertEqual(self.post(IMPORT_URL, filtros_columnas={self.MARCA: ["SON"]}).json()["registros"], 0)

    def test_requires_session(self):
        self.client.logout()
        self.assertEqual(self.post(IMPORT_VALORES, columna="numero_ident").status_code, 403)
        self.assertEqual(self.post(EXPORT_VALORES, columna="numero_ident").status_code, 403)


@override_settings(ALLOWED_HOSTS=["testserver"], CELERY_TASK_ALWAYS_EAGER=True)
class ListasColumnaExportacionesTests(VistaPreviaBase):
    @classmethod
    def setUpTestData(cls):
        source = ArchivoCarga.objects.create(nombre_archivo="x", archivo="cargas/x.zip", tipo_archivo="EXP")
        common = {"archivo_origen": source, "periodo_anio": 2026, "periodo_mes": 2}
        rows = (("D1", "218", "UVAS", "RED GLOBE", "100.50", "10"), ("D1", "218", "CEREZAS", "LAPINS", "300", "20"), ("D2", "225", "UVAS", "THOMPSON", "50", "5"))
        for numero, pais, nombre, atributo, fob, cantidad in rows:
            payload = {"dus_fields": {"NOMBRE": nombre, "ATRIBUTO1": atributo}}
            Exportacion.objects.create(**common, numero_ident=numero, pais_destino_codigo=pais, glosa_mercancia=nombre, valor_fob=fob, cantidad_mercancia=cantidad, valor_fob_dus="450", exportador_codigo="7435", payload_json=payload, texto_producto=texto_producto_exportacion(payload))
        Exportacion.objects.create(archivo_origen=source, periodo_anio=2026, periodo_mes=3, numero_ident="MARZO", pais_destino_codigo="336", glosa_mercancia="OTRO MES", payload_json={"dus_fields": {}})
        bulto = {"archivo_origen": source, "periodo_anio": 2026, "periodo_mes": 2}
        ExportacionBulto.objects.create(**bulto, numero_ident="D1", secuencia="1", cantidad_bultos="7", tipo_bulto_codigo="22")
        ExportacionBulto.objects.create(**bulto, numero_ident="D2", secuencia="1", cantidad_bultos="3", tipo_bulto_codigo="78")
        ExportacionDocTransporte.objects.create(**bulto, numero_ident="D2", secuencia="1", numero_documento="MAEU1", nave="POLAR ARGENTINA", numero_viaje="266103")
        for grupo, codigo, texto in (("paises", "218", "ECUADOR"), ("paises", "225", "EE.UU."), ("paises", "336", "CHINA"), ("tipos_bulto", "22", "CAJA DE CARTON")):
            CatalogoCodigo.objects.create(grupo=grupo, codigo=codigo, glosa=texto)

    def valores(self, columna, **body):
        response = self.post(EXPORT_VALORES, columna=columna, **body)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def ids(self, **filtros):
        return sorted(fila[0] for fila in self.post(EXPORT_URL, filtros_columnas=filtros).json()["filas"])

    def test_lists_cover_catalogs_dus_fields_and_related_tables(self):
        self.assertEqual(self.valores("pais_destino_glosa")["valores"], ["ECUADOR", "EE.UU."])
        self.assertEqual(self.valores("glosa_mercancia")["valores"], ["CEREZAS", "UVAS"])
        self.assertEqual(self.valores("dus:ATRIBUTO1", buscar="red")["valores"], ["RED GLOBE"])
        self.assertEqual(self.valores("naves")["valores"], ["POLAR ARGENTINA"])
        # A code without description shows the code, as the table does.
        self.assertEqual(self.valores("tipos_bulto")["valores"], ["78", "CAJA DE CARTON"])
        self.assertEqual(self.valores("pais_destino_glosa", filtros_columnas={"glosa_mercancia": ["CEREZAS"]})["valores"], ["ECUADOR"])
        cut = self.valores("dus:ATRIBUTO1", limite=1)
        self.assertEqual((cut["valores"], cut["recortada"]), (["LAPINS"], True))

    def test_numeric_and_date_columns_have_no_list(self):
        columnas = ["pais_destino_glosa", "valor_fob", "cantidad_mercancia", "fecha_text", "dia", "total_bultos", "dus:FECHAACEPT", "dus:FOBUS", "naves"]
        tipos = {column["key"]: column["filtro"] for column in self.post(EXPORT_URL, columnas=columnas).json()["columnas"]}
        self.assertEqual([tipos[key] for key in columnas], ["lista", "texto", "texto", "texto", "texto", "texto", "texto", "texto", "lista"])
        self.assertEqual(self.post(EXPORT_VALORES, columna="valor_fob").status_code, 400)

    def test_filters_of_every_kind_of_column(self):
        self.assertEqual(self.ids(pais_destino_glosa=["EE.UU."]), ["D2"])
        self.assertEqual(self.ids(glosa_mercancia=["UVAS"]), ["D1", "D2"])
        self.assertEqual(self.ids(**{"dus:ATRIBUTO1": ["LAPINS"]}), ["D1"])
        self.assertEqual(self.ids(naves=["POLAR ARGENTINA"]), ["D2"])
        self.assertEqual(self.ids(tipos_bulto=["CAJA DE CARTON"]), ["D1", "D1"])
        self.assertEqual(self.ids(valor_fob="100,5"), ["D1"])
        self.assertEqual(self.ids(total_bultos="7"), ["D1", "D1"])

    def test_totals_and_excel_match_the_filters_on_screen(self):
        filtros = {"pais_destino_glosa": ["ECUADOR"], "glosa_mercancia": ["UVAS"]}
        data = self.post(EXPORT_URL, filtros_columnas=filtros).json()
        self.assertEqual((data["registros"], data["totales"]["fob_usd"]), (1, 100.5))
        rows = excel_rows(self, "/api/reportes/exportaciones/exportar/", columnas=["numero_ident", "glosa_mercancia"], filtros_columnas=filtros)
        self.assertEqual(rows, [("D1", "UVAS")])

    def test_export_merchandise_is_not_replaced_by_an_import_alias(self):
        columnas = [column["key"] for column in self.post(EXPORT_URL, columnas=["numero_ident", "glosa_mercancia"]).json()["columnas"]]
        self.assertEqual(columnas, ["numero_ident", "glosa_mercancia"])

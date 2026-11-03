import io
import tempfile
import zipfile
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase

from comercio.models import ArchivoCarga, Importacion
from comercio.processing import materialize_final_rows, store_staging_rows
from comercio.processing import din_importers_by_number
from reportes.models import ImportadorProbable, ReporteSectorial, ReporteSectorialDetalle

FIELDS = (
    "periodo_anio", "periodo_mes", "numero_ident", "importador_probable_sugerido_id", "item", "fecha_text", "aduana_codigo",
    "comuna_importador_codigo", "pais_origen_codigo", "via_transporte_codigo", "partida_arancelaria_codigo",
    "glosa_mercancia", "valor_fob", "valor_flete", "valor_seguro", "valor_cif", "payload_json",
)


def sector_row(importer, rut, mes, anio=2026, dv="", nro_linea=1):
    report, _ = ReporteSectorial.objects.get_or_create(nombre_archivo="r.xlsx", hoja_base="Base", defaults={"rubro": "R", "periodo_anio": anio, "periodo_mes": 3})
    return ReporteSectorialDetalle.objects.create(reporte=report, nro_linea=nro_linea, importador_probable=importer, rut=rut, dv=dv, payload_json={"MES": mes})


def din_line(numero="23441803", unico="10998", item="1", fecaccp="19032026", columns=178):
    parts = [str(index) for index in range(178)]
    parts[0], parts[2], parts[4], parts[5], parts[6] = numero, "48", "03042026", "13101", unico
    parts[21], parts[23], parts[39], parts[132], parts[133], parts[157] = "202", "11", fecaccp, item, "TARJETAS", "85235200"
    parts[64], parts[72] = "3938,16", "4108,24"
    return ";".join(parts[:columns])


class ImportacionesTxtCommandTests(TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        sector_row(ImportadorProbable.objects.create(rut="10998", dv="", nombre="NO INFORMADO"), "10998", "Marzo")

    def zip(self, lines, name="marzo.zip"):
        path = Path(self.dir.name) / name
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("importaciones-marzo-2026/Importaciones - marzo 2026.txt", ("\r\n".join(lines) + "\r\n").encode("latin-1"))
        return path

    def test_rows_match_the_web_upload_path(self):
        lines = [din_line(), din_line(item="2", unico="555"), din_line(item="3", columns=136)]
        call_command("import_importaciones_txt", str(self.zip(lines)), stdout=io.StringIO())
        command_rows = list(Importacion.objects.order_by("id").values(*FIELDS))
        Importacion.objects.all().delete()

        web = ArchivoCarga.objects.create(nombre_archivo="w", archivo="cargas/w.zip", tipo_archivo="IMP", periodo_anio=2026, periodo_mes=3)
        store_staging_rows(web, "\n".join(lines))
        materialize_final_rows(web)
        web_rows = list(Importacion.objects.order_by("id").values(*FIELDS))

        for row in command_rows:
            row["payload_json"].pop("columnas_recibidas", None)
        self.assertEqual(command_rows, web_rows)
        self.assertEqual(command_rows[0]["importador_probable_sugerido_id"], ImportadorProbable.objects.get().id)

    def test_rejects_other_month_and_requires_replace_for_existing_period(self):
        with self.assertRaisesRegex(CommandError, "fuera de 03/2026"):
            call_command("import_importaciones_txt", str(self.zip([din_line(), din_line(item="2", fecaccp="01022026")])), stdout=io.StringIO())
        self.assertFalse(Importacion.objects.exists())
        call_command("import_importaciones_txt", str(self.zip([din_line()])), stdout=io.StringIO())
        out = io.StringIO()
        call_command("import_importaciones_txt", str(self.zip([din_line()])), stdout=out)
        self.assertIn("ya cargado", out.getvalue())
        with self.assertRaisesRegex(CommandError, "--replace"):
            call_command("import_importaciones_txt", str(self.zip([din_line(unico="777")], "otro.zip")), stdout=io.StringIO())
        call_command("import_importaciones_txt", str(self.zip([din_line(unico="777")], "otro.zip")), "--replace", stdout=io.StringIO())
        self.assertEqual(list(Importacion.objects.values_list("numero_ident", flat=True)), ["777"])

    def test_number_from_another_month_is_not_suggested(self):
        out = io.StringIO()
        call_command("import_importaciones_txt", str(self.zip([din_line(fecaccp="19022026")], "febrero.zip")), stdout=out)
        self.assertIsNone(Importacion.objects.get(periodo_mes=2).importador_probable_sugerido)


class ImportadoresPorMesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alfa = ImportadorProbable.objects.create(rut="100", dv="", nombre="ALFA")
        cls.beta = ImportadorProbable.objects.create(rut="100", dv="", nombre="BETA")
        cls.real = ImportadorProbable.objects.create(rut="76123456", dv="0", nombre="RUT REAL")
        sector_row(cls.alfa, "100", "Enero", nro_linea=1)
        sector_row(cls.beta, "100", "Febrero", nro_linea=2)
        sector_row(cls.alfa, "200", "02", nro_linea=3)
        sector_row(cls.real, "76123456", "Febrero", dv="0", nro_linea=4)

    def test_each_month_only_sees_its_own_numbers(self):
        self.assertEqual(din_importers_by_number(2026, 1), {"100": self.alfa})
        self.assertEqual(din_importers_by_number(2026, 2), {"100": self.beta, "200": self.alfa})
        self.assertEqual(din_importers_by_number(2026, 3), {})
        self.assertEqual(din_importers_by_number(2025, 2), {})

    def importacion(self, numero, mes, sugerido=None, **extra):
        source = ArchivoCarga.objects.create(nombre_archivo=f"{numero}-{mes}", archivo="cargas/x.zip", tipo_archivo="IMP", periodo_anio=2026, periodo_mes=mes)
        return Importacion.objects.create(archivo_origen=source, periodo_anio=2026, periodo_mes=mes, numero_ident=numero, importador_probable_sugerido=sugerido, **extra)

    def test_command_recalculates_only_with_aplicar_and_skips_real_ruts(self):
        wrong = self.importacion("100", 1, self.beta)
        unsupported = self.importacion("999", 3, self.alfa)
        missing = self.importacion("200", 2)
        mdb = self.importacion("76123456", 6, self.real, payload_json={"source_format": "MDB_JET3_2015"})

        out = io.StringIO()
        call_command("recalcular_importadores_din", stdout=out)
        self.assertIn("2026-03: 1 filas; con sugerencia 1 -> 0; sin respaldo 1", out.getvalue())
        self.assertIn("2026-06: MDB", out.getvalue())
        unsupported.refresh_from_db()
        self.assertEqual(unsupported.importador_probable_sugerido, self.alfa)

        call_command("recalcular_importadores_din", "--aplicar", stdout=io.StringIO())
        for row, expected in ((wrong, self.alfa), (unsupported, None), (missing, self.alfa), (mdb, self.real)):
            row.refresh_from_db()
            self.assertEqual(row.importador_probable_sugerido, expected)


class TextoProductoTests(TestCase):
    def test_normalizes_and_joins_fields_split_mid_word(self):
        from comercio.busqueda import texto_producto_exportacion, texto_producto_importacion

        din = {"raw_columns": [""] * 133 + ["Pantalla con t", "ODOS SUS", "", "", "", "", "Neumáticos"]}
        self.assertEqual(texto_producto_importacion(din), "PANTALLA CON TODOS SUSNEUMATICOS")
        self.assertEqual(texto_producto_importacion({"legacy_fields": {"MERCADERIA": "MANGO", "ATRI1": "Ñandú"}}), "MANGONANDU")
        self.assertEqual(texto_producto_exportacion({"dus_fields": {"NOMBRE": "uvas", "ATRIBUTO1": "red globe"}}), "UVASRED GLOBE")


class DescripcionTests(TestCase):
    def test_splits_name_brand_and_attributes_and_moves_the_code_to_the_last_attribute(self):
        from comercio.descripcion import separar_descripcion

        cases = [
            # Whole description as one "~" line across fields, cut mid-word.
            (["SIN-CODIGO      ~CASACAS~SEYTEX-F~SINTETICOS~ MODE", "LOS Y COLORES VARIADOS~ PARA D", "AMA~ SON 29.5 DOCENAS~"],
             ["CASACAS", "SEYTEX", "SINTETICOS", "MODELOS Y COLORES VARIADOS", "PARA DAMA", "SON 29.5 DOCENAS SIN-CODIGO", ""]),
            # One attribute per field.
            (["5590007522      ~DISCO DE SUSPENSION", "E.R.D.-F", "DE METAL COMUN", "PARASISTEMA DE TRANSMISION"],
             ["DISCO DE SUSPENSION", "E.R.D.", "DE METAL COMUN", "PARASISTEMA DE TRANSMISION 5590007522", "", "", ""]),
            # "-F" cut between DMARCA and DVARIEDAD.
            (["SIN-CODIGO      ~FILM", "SRF INDUSTRIES (THAILAND) LTD-", "FDE POLIPROPILENO", "EN ROLLOS"],
             ["FILM", "SRF INDUSTRIES (THAILAND) LTD", "DE POLIPROPILENO", "EN ROLLOS SIN-CODIGO", "", "", ""]),
            # Brand without "-F" and the "~" line starting in DMARCA.
            (["SIN-CODIGO      ~PISTOLA", "MARCA WALTHER", "DE AIRE"], ["PISTOLA", "MARCA WALTHER", "DE AIRE", "SIN-CODIGO", "", "", ""]),
            (["SIN_CODIGO      ~ ANILLO SELLADOR", "MERCEDES-F~ DE CAUCHO VULCANIZ", "ADO~ PARA VEHICULO"],
             ["ANILLO SELLADOR", "MERCEDES", "DE CAUCHO VULCANIZADO", "PARA VEHICULO SIN_CODIGO", "", "", ""]),
            # MDB 2015: no product code.
            (["MANGO", "MACHU PICCHU-F", "FRESCO"], ["MANGO", "MACHU PICCHU", "FRESCO", "", "", "", ""]),
        ]
        for fields, expected in cases:
            self.assertEqual(separar_descripcion(fields[0], fields[1:]), expected)

    def test_observed_quantity_and_unit_from_the_first_observation_that_has_them(self):
        from comercio.descripcion import cantidad_observada

        self.assertEqual(cantidad_observada(["00000081.000000 T.M", "", "", ""]), (81.0, "T.M"))
        self.assertEqual(cantidad_observada(["SE SOLIC.REGIMEN PREF.", "001 CANCELA", "00053773.000000 KILOS", ""]), (53773.0, "KILOS"))
        self.assertEqual(cantidad_observada(["1300000008419202502", "", "", ""]), ("", ""))

    def test_brand_not_in_dmarca(self):
        from comercio.descripcion import separar_descripcion

        cases = [
            # DMARCA continues the name; the brand is the next field (MDB 2015).
            (["NEUMATICOS", "DE CAUCHO VULCANIZADO", "SAILUN", "ATREZZO"], ["NEUMATICOS DE CAUCHO VULCANIZADO", "SAILUN", "ATREZZO", "", "", "", ""]),
            # A later field ending in "-F" is the brand.
            (["MANGUERA", "DE CAUCHO VULCANIZADO", "GATES-F", "70695"], ["MANGUERA DE CAUCHO VULCANIZADO", "GATES", "70695", "", "", "", ""]),
            (["MOTOR", "DIESEL", "BRIGGS-F"], ["MOTOR", "BRIGGS", "DIESEL", "", "", "", ""]),
            # No brand when the next field is also a description.
            (["HELICE", "DE PLASTICO", "PARTE DE MOTOR"], ["HELICE DE PLASTICO", "", "PARTE DE MOTOR", "", "", "", ""]),
        ]
        for fields, expected in cases:
            self.assertEqual(separar_descripcion(fields[0], fields[1:]), expected)

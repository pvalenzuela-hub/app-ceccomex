import io
import tempfile
import zipfile
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase

from comercio.models import ArchivoCarga, Importacion
from comercio.processing import materialize_final_rows, store_staging_rows
from reportes.models import ImportadorProbable

FIELDS = (
    "periodo_anio", "periodo_mes", "numero_ident", "importador_probable_sugerido_id", "item", "fecha_text", "aduana_codigo",
    "comuna_importador_codigo", "pais_origen_codigo", "via_transporte_codigo", "partida_arancelaria_codigo",
    "glosa_mercancia", "valor_fob", "valor_flete", "valor_seguro", "valor_cif", "payload_json",
)


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
        ImportadorProbable.objects.create(rut="10998", dv="", nombre="NO INFORMADO")

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

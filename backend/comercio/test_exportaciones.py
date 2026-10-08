import io
import tempfile
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile

from django.test import SimpleTestCase, TestCase, override_settings

from comercio.dus_txt import DUS_COLUMNS, iter_fields, map_doc_transporte, map_exportacion, member_tipo
from comercio.export_loader import export_members, load_member, read_member
from comercio.models import ArchivoCarga, Exportacion, ExportacionBulto, ExportacionDocTransporte


def dus_line(numero="13213653", item="1", fecha="24022026", **overrides):
    row = dict.fromkeys(DUS_COLUMNS, "0")
    row.update({
        "FECHAACEPT": fecha, "NUMEROIDENT": numero, "ADUANA": "39", "NRO_EXPORTADOR": "7435",
        "PUERTOEMB": "906", "PUERTODESEMB": "242", "PAISDESTINO": "218", "VIATRANSPORTE": "1",
        "NUMEROITEM": item, "NOMBRE": "LATA DE ALUMINIO", "CODIGOARANCEL": "76129000",
        "UNIDADMEDIDA": "6", "CANTIDADMERCANCIA": "2905", "FOBUNITARIO": "7,003645",
        "FOBUS": "20345,59", "TOTALVALORFOB": "78391,37", "VALORCIF": "79391,37", "PESOBRUTOITEM": "3705",
    })
    row.update(overrides)
    return ";".join(row[name] for name in DUS_COLUMNS)


def make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, lines in files.items():
            archive.writestr(name, ("\r\n".join(lines) + "\r\n").encode("latin-1"))
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


BASE = "Exportaciones febrero 2026.txt"
BULTOS = "Exportaciones febrero 2026 – Bultos.txt"
DOCS = "Exportaciones febrero 2026 – Documentos de Transporte.txt"


class DusMappingTests(SimpleTestCase):
    def test_maps_spec_positions_and_normalizes_decimal_commas(self):
        data = map_exportacion(dus_line().split(";"), (2026, 2))
        self.assertEqual((data["numero_ident"], data["item"], data["fecha_text"]), ("13213653", "1", "2026-02-24"))
        self.assertEqual((data["aduana_codigo"], data["pais_destino_codigo"], data["partida_arancelaria_codigo"]), ("39", "218", "76129000"))
        self.assertEqual((data["valor_fob"], data["valor_fob_unitario"], data["valor_fob_dus"]), ("20345.59", "7.003645", "78391.37"))
        self.assertEqual(data["payload_json"]["dus_fields"]["NRO_EXPORTADOR"], "7435")
        self.assertFalse(data["registro_incompleto"])

    def test_keeps_rows_truncated_after_nombre_flagged_as_incomplete(self):
        fields = dus_line().split(";")[: DUS_COLUMNS.index("NOMBRE") + 1]
        data = map_exportacion(fields, (2026, 2))
        self.assertTrue(data["registro_incompleto"])
        self.assertEqual((data["partida_arancelaria_codigo"], data["valor_fob"]), ("", ""))

    def test_rejects_other_period_bad_amounts_and_short_rows(self):
        for fields in (
            dus_line(fecha="01032026").split(";"),
            dus_line(FOBUS="12a").split(";"),
            dus_line().split(";")[:40],
        ):
            with self.subTest(fields=fields[:2]), self.assertRaises(ValueError):
                map_exportacion(fields, (2026, 2))

    def test_document_without_viaje_and_zero_date(self):
        data = map_doc_transporte("13238414;05022026;1;CL-4691;00000000;COSCO".split(";"), (2026, 2))
        self.assertTrue(data["registro_incompleto"])
        self.assertEqual((data["fecha_documento_text"], data["numero_viaje"]), ("", ""))

    def test_splits_only_on_line_feed_and_decodes_latin1(self):
        rows = list(iter_fields(io.BytesIO("a;b\rc;\xd1\t\r\nd;e   \n".encode("latin-1"))))
        self.assertEqual(rows, [(1, ["a", "b c", "\xd1"]), (2, ["d", "e"])])

    def test_member_classification(self):
        self.assertEqual([member_tipo(name) for name in (BASE, BULTOS, DOCS, "otro.csv")], ["EXP_BASE", "EXP_BULTO", "EXP_DOC", None])

    def test_duplicate_item_rejected(self):
        archive = make_zip({BASE: [dus_line(), dus_line()]})
        with self.assertRaisesRegex(ValueError, "duplicada"):
            read_member(archive, BASE, "EXP_BASE")


class ExportLoaderTests(TestCase):
    def archive(self):
        return make_zip({
            DOCS: ["13213653;24022026;1;MAEU263763771;10012026;POLAR ARGENTINA;266103", "99999999;24022026;1;X;00000000;;"],
            BULTOS: ["13213653;24022026;1;78;1;"],
            BASE: [dus_line(), dus_line(item="2", FOBUS="100")],
        })

    def load_all(self, archive, **kwargs):
        return {tipo: load_member(archive, member, tipo, archivo_path="cargas/x.zip", **kwargs)[1] for member, tipo in export_members(archive)}

    def test_loads_three_files_base_first_and_reports_orphans(self):
        archive = self.archive()
        self.assertEqual([tipo for _, tipo in export_members(archive)], ["EXP_BASE", "EXP_BULTO", "EXP_DOC"])
        summaries = self.load_all(archive)
        self.assertEqual((Exportacion.objects.count(), ExportacionBulto.objects.count(), ExportacionDocTransporte.objects.count()), (2, 1, 2))
        self.assertEqual(summaries["EXP_DOC"]["dus_sin_base"], 1)
        self.assertEqual(set(ArchivoCarga.objects.values_list("estado", flat=True)), {"PROCESADO"})
        self.assertEqual(ExportacionDocTransporte.objects.get(numero_ident="13213653").fecha_documento_text, "2026-01-10")

    def test_repeat_is_skipped_and_different_file_needs_replace(self):
        self.load_all(self.archive())
        self.assertEqual(self.load_all(self.archive())["EXP_BASE"]["ya_cargado"], 1)
        self.assertEqual(Exportacion.objects.count(), 2)
        other = make_zip({BASE: [dus_line(item="7")]})
        with self.assertRaisesRegex(ValueError, "--replace"):
            load_member(other, BASE, "EXP_BASE", archivo_path="cargas/y.zip")
        load_member(other, BASE, "EXP_BASE", archivo_path="cargas/y.zip", replace=True)
        self.assertEqual(list(Exportacion.objects.values_list("item", flat=True)), ["7"])

    def test_invalid_line_rolls_back_the_whole_file(self):
        archive = make_zip({BASE: [dus_line(), dus_line(item="2", fecha="01012026")]})
        with self.assertRaisesRegex(ValueError, "línea 2"):
            load_member(archive, BASE, "EXP_BASE", archivo_path="cargas/z.zip")
        self.assertFalse(Exportacion.objects.exists())
        self.assertFalse(ArchivoCarga.objects.exists())


class ExportUploadViewTests(TestCase):
    def test_upload_loads_only_the_txt_matching_the_selected_type(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(BASE, dus_line() + "\r\n")
            archive.writestr(BULTOS, "13213653;24022026;1;78;1;\r\n")
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media, CELERY_TASK_ALWAYS_EAGER=True):
            upload = SimpleUploadedFile("exportaciones-febrero-2026.zip", buffer.getvalue(), content_type="application/zip")
            response = self.client.post("/api/comercio/upload/", {"archivo": upload, "tipo_archivo": "EXP_BULTO"})
        self.assertIn(response.status_code, (201, 202))
        carga = ArchivoCarga.objects.get()
        self.assertEqual((carga.estado, carga.total_ok, carga.periodo_mes), ("PROCESADO", 1, 2))
        self.assertEqual((ExportacionBulto.objects.count(), Exportacion.objects.count()), (1, 0))

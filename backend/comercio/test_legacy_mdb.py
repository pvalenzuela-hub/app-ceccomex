from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from comercio.legacy_mdb import LEGACY_COLUMNS, map_importacion
from comercio.management.commands.import_legacy_mdb import Command, read_month
from comercio.models import ArchivoCarga, Importacion
from reportes.views import _column_value, _filtered_importaciones


def example_row(**overrides):
    row = dict.fromkeys(LEGACY_COLUMNS, "")
    row.update({
        "PERIODO": "201501", "NUM_IDEN": "12345", "NUM_ITEM": "2",
        "FEC_ACE": "2012015", "COD_ADU": "11", "PAI_ORI": "219",
        "VIA": "7", "COD_AAR": "08045000", "MERCADERIA": "MANGO",
        "RUT": "12345678", "DV": "9", "IMPORT": "IMPORTADOR EJEMPLO",
        "REG_IMP": "1", "FOB_ITEM": "250.75", "FLE_ITEM": "12.5",
        "SEG_ITEM": "0.1", "CIF_ITEM": "263.35", "VAL_FOB": "9999",
        "VAL_FLETE": "888", "MON_SEG": "77", "CIF_TOTAL": "11000",
    })
    row.update(overrides)
    return row


class LegacyMDBMappingTests(SimpleTestCase):
    def test_preserves_named_fields_and_uses_item_values_instead_of_header_totals(self):
        data = map_importacion(example_row(), 1)
        self.assertEqual(data["fecha_text"], "2015-01-02")
        self.assertEqual(str(data["fecha_date"]), "2015-01-02")
        self.assertEqual(data["partida_arancelaria_codigo"], "08045000")
        self.assertEqual(
            [data[key] for key in ("valor_fob", "valor_flete", "valor_seguro", "valor_cif")],
            ["250.75", "12.5", "0.1", "263.35"],
        )
        self.assertEqual(data["payload_json"]["legacy_fields"]["VAL_FOB"], "9999")
        self.assertNotIn("raw_columns", data["payload_json"])
        self.assertEqual(data["comuna_importador_codigo"], "")

    def test_rejects_wrong_month_invalid_date_and_invalid_item_amount(self):
        for changes in ({"PERIODO": "201502"}, {"FEC_ACE": "3212015"}, {"FOB_ITEM": "nan"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                map_importacion(example_row(**changes), 1)

    def test_legacy_report_uses_named_fields_without_fabricating_txt_positions(self):
        data = map_importacion(example_row(), 1)
        row = SimpleNamespace(**data, importador_probable_sugerido=None)
        self.assertEqual(_column_value(row, "mdb:FOB_ITEM", {}), "250.75")
        self.assertEqual(_column_value(row, "raw:54", {}), "1")
        self.assertEqual(_column_value(row, "raw:157", {}), "08045000")
        self.assertEqual(_column_value(row, "raw:6", {}), "")
        self.assertEqual(_column_value(row, "importador_probable", {}), "IMPORTADOR EJEMPLO")

    def test_full_month_checks_count_and_duplicate_item_keys(self):
        @contextmanager
        def rows(*args, **kwargs):
            yield iter([example_row(), example_row(NUM_IDEN="12346", NUM_ITEM="1")])

        with patch("comercio.management.commands.import_legacy_mdb.export_rows", rows), patch(
            "comercio.management.commands.import_legacy_mdb.EXPECTED_ROWS", {1: 2}
        ):
            summary = read_month(None, "IM201501.mdb", 1, temp_dir=None)
            self.assertEqual(summary["rows"], 2)
            with patch("comercio.management.commands.import_legacy_mdb.export_rows") as exported:
                exported.return_value.__enter__.return_value = iter([example_row(), example_row()])
                with self.assertRaisesRegex(ValueError, "duplicados"):
                    read_month(None, "IM201501.mdb", 1, temp_dir=None)


class LegacyMDBLoadTests(TestCase):
    @patch("comercio.management.commands.import_legacy_mdb.EXPECTED_ROWS", {1: 2})
    def test_per_month_load_is_atomic_reconciled_and_idempotent(self):
        archive = SimpleNamespace(getinfo=lambda name: SimpleNamespace(CRC=1234567))
        month = "IM201501.mdb"
        command = Command()
        source = Path("/app/cargas/historico.zip")

        def fail_after_first_batch(*args, **kwargs):
            kwargs["on_batch"]([map_importacion(example_row(), 1)])
            raise ValueError("error de lectura")

        with patch("comercio.management.commands.import_legacy_mdb.read_month", fail_after_first_batch):
            with self.assertRaisesRegex(ValueError, "error de lectura"):
                command.load_month(archive, source, month, 1, None, 500)
        self.assertFalse(ArchivoCarga.objects.exists())
        self.assertFalse(Importacion.objects.exists())

        def two_rows(*args, **kwargs):
            kwargs["on_batch"]([
                map_importacion(example_row(), 1),
                map_importacion(example_row(NUM_IDEN="12346"), 1),
            ])
            return {"rows": 2}

        with patch("comercio.management.commands.import_legacy_mdb.read_month", two_rows):
            command.load_month(archive, source, month, 1, None, 500)
            command.load_month(archive, source, month, 1, None, 500)
        self.assertEqual(ArchivoCarga.objects.count(), 1)
        self.assertEqual(Importacion.objects.count(), 2)
        self.assertEqual(ArchivoCarga.objects.get().estado, "PROCESADO")

    def test_regimen_filter_matches_historic_and_current_sources(self):
        source = ArchivoCarga.objects.create(nombre_archivo="mixed", archivo="cargas/example.zip", tipo_archivo="IMP")
        modern = [""] * 178
        modern[54] = "1"
        Importacion.objects.create(archivo_origen=source, numero_ident="txt", payload_json={"raw_columns": modern})
        Importacion.objects.create(
            archivo_origen=source,
            numero_ident="mdb",
            payload_json={"legacy_fields": {"REG_IMP": "1"}},
        )
        Importacion.objects.create(
            archivo_origen=source,
            numero_ident="other",
            payload_json={"legacy_fields": {"REG_IMP": "2"}},
        )
        results = _filtered_importaciones({"regimenes": ["1"]}, None, None)
        self.assertCountEqual(results.values_list("numero_ident", flat=True), ["txt", "mdb"])

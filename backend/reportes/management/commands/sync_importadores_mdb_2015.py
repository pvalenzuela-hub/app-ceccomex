"""Enrich the importer catalog from the already loaded 2015 MDB records."""

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from comercio.legacy_mdb import EXPECTED_ROWS, SOURCE_FORMAT
from comercio.models import Importacion
from reportes.models import ImportadorProbable


ORIGEN = "MDB_2015"
TEMP_TABLE = "mdb_2015_importador_map"


def normalize(value):
    return "".join(char for char in str(value or "").upper() if char.isalnum())


def valid_rut(rut, dv):
    if not rut.isdecimal() or not 7 <= len(rut) <= 8 or len(dv) != 1 or dv not in "0123456789K":
        return False
    result = (11 - sum(int(digit) * (index % 6 + 2) for index, digit in enumerate(reversed(rut))) % 11) % 11
    return dv == ("K" if result == 10 else str(result))


def source_rows():
    return (
        Importacion.objects.filter(
            periodo_anio=2015,
            periodo_mes__in=EXPECTED_ROWS,
            payload_json__source_format=SOURCE_FORMAT,
        )
        .order_by()
        .values_list(
            "payload_json__legacy_fields__RUT",
            "payload_json__legacy_fields__DV",
            "payload_json__legacy_fields__IMPORT",
        )
        .distinct()
        .iterator(chunk_size=2000)
    )


def candidates():
    names_by_key = defaultdict(dict)
    invalid_keys = set()
    missing_names = set()
    for raw_rut, raw_dv, raw_name in source_rows():
        key = (normalize(raw_rut), normalize(raw_dv))
        if not key[0] or not key[1]:
            continue
        if not valid_rut(*key):
            invalid_keys.add(key)
            continue
        name = " ".join(str(raw_name or "").upper().split())
        if not name:
            missing_names.add(key)
            continue
        names_by_key[key].setdefault(name.casefold(), name)
    return names_by_key, invalid_keys, missing_names


def catalog_by_key():
    result = {}
    for pk, rut, dv in ImportadorProbable.objects.order_by("id").values_list("id", "rut", "dv").iterator(chunk_size=1000):
        if rut and dv:
            result.setdefault((normalize(rut), normalize(dv)), pk)
    return result


def update_sqlite_links(mapping, batch_size):
    """Portable path for tests and development; production uses one SQL join per month."""
    linked = {}
    for month in EXPECTED_ROWS:
        updated = 0
        buffer = []
        with transaction.atomic():
            rows = Importacion.objects.filter(
                periodo_anio=2015,
                periodo_mes=month,
                payload_json__source_format=SOURCE_FORMAT,
                importador_probable_sugerido__isnull=True,
            ).values_list("pk", "payload_json").iterator(chunk_size=batch_size)
            for pk, payload in rows:
                fields = payload.get("legacy_fields", {})
                rut, dv = normalize(fields.get("RUT")), normalize(fields.get("DV"))
                importer_id = mapping.get((rut, dv)) if valid_rut(rut, dv) else None
                if importer_id:
                    buffer.append(Importacion(pk=pk, importador_probable_sugerido_id=importer_id))
                if len(buffer) >= batch_size:
                    Importacion.objects.bulk_update(buffer, ["importador_probable_sugerido"], batch_size=batch_size)
                    updated += len(buffer)
                    buffer.clear()
            if buffer:
                Importacion.objects.bulk_update(buffer, ["importador_probable_sugerido"], batch_size=batch_size)
                updated += len(buffer)
        linked[month] = updated
    return linked


def update_postgresql_links(mapping, batch_size):
    """Use a temporary key map so 1.7 million JSON rows are not loaded into Python."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE TEMP TABLE {TEMP_TABLE} (rut text, dv text, importer_id bigint, PRIMARY KEY (rut, dv)) ON COMMIT PRESERVE ROWS"
        )
    try:
        items = list(mapping.items())
        for start in range(0, len(items), batch_size):
            chunk = items[start:start + batch_size]
            args = [part for (rut, dv), importer_id in chunk for part in (rut, dv, importer_id)]
            placeholders = ",".join(["(%s,%s,%s)"] * len(chunk))
            with connection.cursor() as cursor:
                cursor.execute(f"INSERT INTO {TEMP_TABLE} (rut,dv,importer_id) VALUES {placeholders}", args)
        with connection.cursor() as cursor:
            cursor.execute(f"ANALYZE {TEMP_TABLE}")

        linked = {}
        for month in EXPECTED_ROWS:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""UPDATE comercio_importacion AS imp
                        SET importador_probable_sugerido_id = mapping.importer_id
                        FROM {TEMP_TABLE} AS mapping
                        WHERE imp.periodo_anio = 2015 AND imp.periodo_mes = %s
                          AND imp.importador_probable_sugerido_id IS NULL
                          AND imp.payload_json->>'source_format' = %s
                          AND regexp_replace(upper(imp.payload_json->'legacy_fields'->>'RUT'), '[^A-Z0-9]', '', 'g') = mapping.rut
                          AND regexp_replace(upper(imp.payload_json->'legacy_fields'->>'DV'), '[^A-Z0-9]', '', 'g') = mapping.dv""",
                        [month, SOURCE_FORMAT],
                    )
                    linked[month] = cursor.rowcount
        return linked
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {TEMP_TABLE}")


class Command(BaseCommand):
    help = "Agrega importadores inequívocos de los MDB 2015 y vincula sus importaciones existentes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Calcula candidatos sin escribir en la base.")
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if not 1 <= batch_size <= 2000:
            raise CommandError("--batch-size debe estar entre 1 y 2000")
        names_by_key, invalid, missing = candidates()
        existing = catalog_by_key()
        ambiguous = {key for key, names in names_by_key.items() if len(names) != 1}
        additions = [
            (rut, dv, next(iter(names.values())))
            for (rut, dv), names in sorted(names_by_key.items())
            if len(names) == 1 and (rut, dv) not in existing
        ]
        self.stdout.write(
            f"Claves válidas: {len(names_by_key)}; sin nombre: {len(missing)}; "
            f"RUT inválidos: {len(invalid)}; con nombres distintos: {len(ambiguous)} "
            f"({len(ambiguous - existing.keys())} sin entrada previa); nuevas: {len(additions)}"
        )
        if options["dry_run"]:
            return

        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [201507])
            existing = catalog_by_key()
            additions = [
                ImportadorProbable(rut=rut, dv=dv, nombre=name, origen=ORIGEN)
                for rut, dv, name in additions if (rut, dv) not in existing
            ]
            ImportadorProbable.objects.bulk_create(additions, batch_size=batch_size, ignore_conflicts=True)
        mapping = {key: pk for key, pk in catalog_by_key().items() if key in names_by_key and valid_rut(*key)}
        self.stdout.write(f"Catálogo: {len(additions)} entradas añadidas; {len(mapping)} claves vinculables.")
        if connection.vendor == "postgresql":
            linked = update_postgresql_links(mapping, batch_size)
        else:
            linked = update_sqlite_links(mapping, batch_size)
        for month, count in linked.items():
            self.stdout.write(f"2015-{month:02d}: {count} importaciones vinculadas.")
        self.stdout.write(f"Vínculos nuevos: {sum(linked.values())}.")

"""Backfill `texto_producto` for rows loaded before the column existed. Resumable: one commit per id batch."""

import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from comercio.busqueda import DIN_PRODUCT_POSITIONS, DUS_PRODUCT_FIELDS, MDB_PRODUCT_FIELDS, normalizar


# Only the product fields are extracted in SQL, so the large JSON payloads never reach Python.
SOURCES = {
    "importaciones": (
        "comercio_importacion",
        [f"payload_json #>> '{{raw_columns,{index}}}'" for index in DIN_PRODUCT_POSITIONS]
        + [f"payload_json #>> '{{legacy_fields,{name}}}'" for name in MDB_PRODUCT_FIELDS],
    ),
    "exportaciones": ("comercio_exportacion", [f"payload_json #>> '{{dus_fields,{name}}}'" for name in DUS_PRODUCT_FIELDS]),
}


class Command(BaseCommand):
    help = "Calcula texto_producto (búsqueda de productos) en importaciones y exportaciones ya cargadas."

    def add_arguments(self, parser):
        parser.add_argument("--tabla", choices=sorted(SOURCES), action="append")
        parser.add_argument("--lote", type=int, default=5000)
        parser.add_argument("--desde-id", type=int, default=0, help="Retomar desde este id.")
        parser.add_argument("--solo-vacios", action="store_true", help="Solo filas con texto_producto vacío.")

    def handle(self, *args, **options):
        for name in options["tabla"] or sorted(SOURCES, reverse=True):
            self.fill(name, *SOURCES[name], options)

    def fill(self, name, table, expressions, options):
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT coalesce(max(id), 0), count(*) FROM {table}")
            max_id, total = cursor.fetchone()
        last_id, done, batches, started = options["desde_id"], 0, 0, time.time()
        only_empty = "AND texto_producto = ''" if options["solo_vacios"] else ""
        while last_id < max_id:
            upper = last_id + options["lote"]
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT id, {', '.join(expressions)} FROM {table} WHERE id > %s AND id <= %s {only_empty}",
                    [last_id, upper],
                )
                rows = [(row[0], normalizar("".join(part or "" for part in row[1:]))) for row in cursor.fetchall()]
                if rows:
                    values = ", ".join(["(%s, %s)"] * len(rows))
                    cursor.execute(
                        f"UPDATE {table} AS t SET texto_producto = v.texto FROM (VALUES {values}) AS v(id, texto) WHERE t.id = v.id",
                        [item for row in rows for item in row],
                    )
            done, last_id, batches = done + len(rows), upper, batches + 1
            if batches % 40 == 0:
                self.stdout.write(f"{name}: {done:,}/{total:,} filas, id {last_id}, {time.time() - started:.0f}s")
                self.stdout.flush()
        self.stdout.write(f"{name}: {done:,} filas actualizadas en {time.time() - started:.0f}s")

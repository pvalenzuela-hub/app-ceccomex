"""Validate or load IM201501-IM201506 from the original Access databases."""

from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from comercio.legacy_mdb import EXPECTED_ROWS, export_rows, map_importacion, member_month
from comercio.models import ArchivoCarga, Importacion
from reportes.models import ImportadorProbable


def normalize_rut(value):
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def importers_by_rut():
    matches = {}
    for importer in ImportadorProbable.objects.order_by("id").iterator(chunk_size=1000):
        key = normalize_rut(f"{importer.rut}{importer.dv}")
        if importer.rut and importer.dv and key:
            matches.setdefault(key, importer.pk)
    return matches


def read_month(archive, member, month, *, temp_dir, on_batch=None, batch_size=500, importers=None):
    """Validate every row and emit bounded batches only if on_batch is supplied."""
    seen = set()
    missing_dv = 0
    unmatched_importers = 0
    count = 0
    batch = []
    with export_rows(archive, member, temp_dir=temp_dir) as rows:
        for row in rows:
            count += 1
            if None in row:
                raise ValueError(f"Columna CSV adicional en {member}, fila {count}")
            try:
                data = map_importacion(row, month)
            except (ValueError, KeyError, AttributeError) as exc:
                raise ValueError(f"{member}, fila {count}: {exc}") from exc
            key = (data["numero_ident"], data["item"])
            if key in seen:
                raise ValueError(f"{member}, fila {count}: NUM_IDEN/NUM_ITEM duplicados")
            seen.add(key)
            if not row["DV"].strip():
                missing_dv += 1
            rut_key = normalize_rut(f"{row['RUT']}{row['DV']}") if row["RUT"].strip() and row["DV"].strip() else ""
            if rut_key and importers is not None:
                data["importador_probable_sugerido_id"] = importers.get(rut_key)
                if not data["importador_probable_sugerido_id"]:
                    unmatched_importers += 1
            if on_batch is not None:
                batch.append(data)
                if len(batch) >= batch_size:
                    on_batch(batch)
                    batch = []
    if batch:
        on_batch(batch)
    if count != EXPECTED_ROWS[month]:
        raise ValueError(f"{member}: {count} filas, se esperaban {EXPECTED_ROWS[month]}")
    return Counter(rows=count, missing_dv=missing_dv, unmatched_importers=unmatched_importers)


class Command(BaseCommand):
    help = "Valida o carga las seis bases MDB de importaciones de enero-junio 2015."

    def add_arguments(self, parser):
        parser.add_argument("zip_path", type=Path)
        parser.add_argument("--validate-only", action="store_true")
        parser.add_argument("--month", type=int, choices=sorted(EXPECTED_ROWS), action="append")
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--temp-dir", type=Path, help="Directorio temporal con espacio para un MDB (hasta 403 MB).")

    def handle(self, *args, **options):
        zip_path = options["zip_path"]
        if not zip_path.is_file():
            raise CommandError(f"No existe: {zip_path}")
        if options["batch_size"] < 1 or options["batch_size"] > 2000:
            raise CommandError("--batch-size debe estar entre 1 y 2000")
        temp_dir = options["temp_dir"]
        if temp_dir is not None and not temp_dir.is_dir():
            raise CommandError(f"No existe el directorio temporal: {temp_dir}")
        try:
            with ZipFile(zip_path) as archive:
                infos = archive.infolist()
                members = {member_month(info.filename): info.filename for info in infos}
                if len(infos) != 6 or len(members) != 6:
                    raise ValueError("El ZIP debe contener exactamente las seis bases IM201501-IM201506.mdb")
                for month in sorted(set(options["month"] or EXPECTED_ROWS)):
                    member = members[month]
                    if options["validate_only"]:
                        summary = read_month(archive, member, month, temp_dir=temp_dir)
                    else:
                        summary = self.load_month(archive, zip_path, member, month, temp_dir, options["batch_size"])
                    self.stdout.write(f"{member}: {dict(summary)}")
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(str(exc)) from exc

    def load_month(self, archive, zip_path, member, month, temp_dir, batch_size):
        name = f"MDB2015:{member}:{archive.getinfo(member).CRC:08x}"
        importers = importers_by_rut()
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [201500 + month])
            source = ArchivoCarga.objects.filter(nombre_archivo=name).first()
            existing = Importacion.objects.filter(periodo_anio=2015, periodo_mes=month)
            if source and source.estado == "PROCESADO" and existing.filter(archivo_origen=source).count() == EXPECTED_ROWS[month]:
                self.stdout.write(f"{member}: ya cargado y conciliado, se omite.")
                return Counter(rows=EXPECTED_ROWS[month], already_loaded=1)
            if source or existing.exists():
                raise ValueError(f"Ya existen registros o una carga para {member}; revisar antes de reintentar")
            source = ArchivoCarga.objects.create(
                nombre_archivo=name,
                archivo=f"cargas/{zip_path.name}",
                tipo_archivo="IMP",
                estado="PROCESANDO",
                periodo_anio=2015,
                periodo_mes=month,
                total_registros=EXPECTED_ROWS[month],
                observacion=f"Fuente MDB Jet 3: {member}; valores por ítem; CRC {archive.getinfo(member).CRC:08x}",
            )
            loaded = 0

            def insert_batch(batch):
                nonlocal loaded
                Importacion.objects.bulk_create(
                    (Importacion(archivo_origen=source, **data) for data in batch), batch_size=batch_size,
                )
                loaded += len(batch)
                if loaded % 5000 == 0:
                    ArchivoCarga.objects.filter(pk=source.pk).update(total_procesados=loaded, total_ok=loaded)
                    self.stdout.write(f"{member}: {loaded}/{EXPECTED_ROWS[month]}")

            summary = read_month(
                archive, member, month, temp_dir=temp_dir, on_batch=insert_batch,
                batch_size=batch_size, importers=importers,
            )
            if loaded != EXPECTED_ROWS[month] or existing.filter(archivo_origen=source).count() != loaded:
                raise ValueError(f"Conciliación fallida en {member}: {loaded} filas creadas")
            source.estado = "PROCESADO"
            source.total_procesados = loaded
            source.total_ok = loaded
            source.save(update_fields=["estado", "total_procesados", "total_ok"])
            return summary

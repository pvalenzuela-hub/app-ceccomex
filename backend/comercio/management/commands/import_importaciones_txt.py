"""Validate or load monthly DIN import TXT files (178 columns) streamed from ZIP archives.

Produces the same Importacion rows as the web upload (parse_txt_line + materialize_final_rows)
without the staging table, in one transaction per file.
"""

from collections import Counter
from datetime import datetime
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from comercio.models import ArchivoCarga, Importacion
from comercio.processing import importers_by_key, normalize_rut, parse_txt_line


DIN_COLUMNS = 178
FECACEP, NUMITEM = 39, 132  # positions in doc-req/import/descripcion-y-estructura-de-datos-din.xlsx
# Aduana cuts some fixed-width lines (seen: 135-137 columns); they are kept and flagged.
MIN_COLUMNS = 120
LOCK_BASE = 4_000_000


def iter_lines(stream):
    """(line_number, line) for data lines, skipping what the web upload skips (headers "00;", short lines)."""
    for number, raw in enumerate(stream, start=1):
        line = raw.rstrip(b"\r\n").decode("latin-1").replace("\r", " ").strip()
        if line and not line.startswith("00;") and line.count(";") >= 20:
            yield number, line


def period_of(parts):
    value = parts[FECACEP].strip() if len(parts) > FECACEP else ""
    try:
        fecha = datetime.strptime(value.zfill(8), "%d%m%Y")
    except ValueError as exc:
        raise ValueError(f"FECACEP inválida: {value!r}") from exc
    return fecha.year, fecha.month


def read_member(archive, member, *, on_batch=None, batch_size=1000, importers=None):
    with archive.open(member) as stream:
        first = next(iter_lines(stream), None)
    if first is None:
        raise ValueError(f"{member}: sin líneas de datos")
    periodo = period_of(first[1].split(";"))
    seen = set()
    summary = Counter()
    batch = []
    with archive.open(member) as stream:
        for number, line in iter_lines(stream):
            data = parse_txt_line("IMP", line)
            parts = data["raw_columns"]
            if not MIN_COLUMNS <= len(parts) <= DIN_COLUMNS:
                raise ValueError(f"{member}, línea {number}: {len(parts)} columnas, se esperaban {DIN_COLUMNS}")
            if period_of(parts) != periodo:
                raise ValueError(f"{member}, línea {number}: FECACEP {parts[FECACEP]} fuera de {periodo[1]:02d}/{periodo[0]}")
            key = (parts[0], parts[6], parts[NUMITEM] if len(parts) > NUMITEM else "")
            if key in seen:
                raise ValueError(f"{member}, línea {number}: clave duplicada {key}")
            seen.add(key)
            if len(parts) < DIN_COLUMNS:
                data["columnas_recibidas"] = len(parts)
                summary["incompletas"] += 1
            summary["filas"] += 1
            if on_batch is not None:
                importer = importers.get(normalize_rut(data["numero_ident"]))
                summary["con_importador"] += int(importer is not None)
                batch.append(Importacion(
                    periodo_anio=periodo[0],
                    periodo_mes=periodo[1],
                    numero_ident=data["numero_ident"],
                    importador_probable_sugerido=importer,
                    item=data["item"],
                    fecha_text=data["fecha"],
                    aduana_codigo=data["aduana_codigo"],
                    comuna_importador_codigo=data["comuna_importador_codigo"],
                    pais_origen_codigo=data["pais_origen_codigo"],
                    via_transporte_codigo=data["via_transporte_codigo"],
                    partida_arancelaria_codigo=data["partida_arancelaria_codigo"],
                    glosa_mercancia=data["glosa_mercancia"],
                    valor_fob=data["valor_fob"],
                    valor_flete=data["valor_flete"],
                    valor_seguro=data["valor_seguro"],
                    valor_cif=data["valor_cif"],
                    payload_json=data,
                ))
                if len(batch) >= batch_size:
                    on_batch(batch)
                    batch = []
    if batch:
        on_batch(batch)
    return periodo, summary


class Command(BaseCommand):
    help = "Valida o carga TXT mensuales de importaciones DIN (178 columnas) desde ZIP, sin staging."

    def add_arguments(self, parser):
        parser.add_argument("zip_paths", nargs="+", type=Path)
        parser.add_argument("--validate-only", action="store_true")
        parser.add_argument("--replace", action="store_true", help="Reemplaza importaciones existentes del mismo período.")
        parser.add_argument("--batch-size", type=int, default=1000)

    def handle(self, *args, **options):
        if not 1 <= options["batch_size"] <= 5000:
            raise CommandError("--batch-size debe estar entre 1 y 5000")
        for zip_path in options["zip_paths"]:
            if not zip_path.is_file():
                raise CommandError(f"No existe: {zip_path}")
        try:
            for zip_path in options["zip_paths"]:
                with ZipFile(zip_path) as archive:
                    members = [info.filename for info in archive.infolist() if info.filename.lower().endswith(".txt")]
                    if len(members) != 1:
                        raise ValueError(f"{zip_path.name}: se esperaba un TXT, hay {len(members)}")
                    if options["validate_only"]:
                        periodo, summary = read_member(archive, members[0])
                    else:
                        periodo, summary = self.load(archive, zip_path, members[0], options)
                    self.stdout.write(f"IMP {periodo[1]:02d}/{periodo[0]} {members[0]}: {dict(summary)}")
        except (OSError, ValueError, BadZipFile) as exc:
            raise CommandError(str(exc)) from exc

    def load(self, archive, zip_path, member, options):
        crc = archive.getinfo(member).CRC
        with archive.open(member) as stream:
            periodo = period_of(next(iter_lines(stream))[1].split(";"))
        nombre = f"DIN:{periodo[0]}{periodo[1]:02d}:{crc:08x}"
        importers = importers_by_key()
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_BASE + periodo[0] * 100 + periodo[1]])
            existing = Importacion.objects.filter(periodo_anio=periodo[0], periodo_mes=periodo[1])
            previous = ArchivoCarga.objects.filter(tipo_archivo="IMP", periodo_anio=periodo[0], periodo_mes=periodo[1])
            loaded = previous.filter(estado="PROCESADO", observacion__contains=nombre).first()
            if loaded and not options["replace"] and existing.count() == loaded.total_ok:
                self.stdout.write(f"{member}: ya cargado ({loaded.total_ok} filas), se omite.")
                return periodo, Counter(filas=loaded.total_ok, ya_cargado=1)
            if existing.exists():
                if not options["replace"]:
                    raise ValueError(f"Ya existen {existing.count()} importaciones de {periodo[1]:02d}/{periodo[0]}; use --replace para reemplazarlas")
                self.stdout.write(f"{member}: reemplazando {existing.delete()[0]} registros previos")
                previous.update(estado="ERROR", observacion="Reemplazada por una carga posterior del mismo período")
            source = ArchivoCarga.objects.create(
                nombre_archivo=member.rsplit("/", 1)[-1], archivo=f"cargas/{zip_path.name}", tipo_archivo="IMP",
                estado="PROCESANDO", periodo_anio=periodo[0], periodo_mes=periodo[1],
                observacion=f"{nombre} | Fuente TXT DIN: {member}; sin staging",
            )
            inserted = 0

            def insert(batch):
                nonlocal inserted
                for row in batch:
                    row.archivo_origen = source
                Importacion.objects.bulk_create(batch, batch_size=options["batch_size"])
                inserted += len(batch)
                if inserted % 50000 < len(batch):
                    self.stdout.write(f"{member}: {inserted} filas")

            _, summary = read_member(archive, member, on_batch=insert, batch_size=options["batch_size"], importers=importers)
            if inserted != summary["filas"] or existing.count() != inserted:
                raise ValueError(f"Conciliación fallida en {member}: {inserted} insertadas de {summary['filas']} leídas")
            source.estado = "PROCESADO"
            source.total_registros = source.total_procesados = source.total_ok = inserted
            source.observacion += f" | {inserted} filas, {summary['incompletas']} truncadas en origen, {summary['con_importador']} con importador"
            source.save(update_fields=["estado", "total_registros", "total_procesados", "total_ok", "observacion"])
            return periodo, summary

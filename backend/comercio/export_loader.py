"""Validate and load monthly DUS export TXT files streamed from a ZIP, one transaction per file."""

from collections import Counter

from django.db import connection, transaction

from comercio.dus_txt import KEY_FIELDS, MAPPERS, TIPOS, detect_period, iter_fields, member_tipo
from comercio.models import ArchivoCarga, Exportacion, ExportacionBulto, ExportacionDocTransporte


MODELS = {"EXP_BASE": Exportacion, "EXP_BULTO": ExportacionBulto, "EXP_DOC": ExportacionDocTransporte}
LOCK_BASE = {"EXP_BASE": 1_000_000, "EXP_BULTO": 2_000_000, "EXP_DOC": 3_000_000}


def export_members(archive, tipo=None):
    """[(member, tipo)] with the base file first so bultos/documentos can be reconciled against it."""
    found = [(info.filename, member_tipo(info.filename)) for info in archive.infolist() if not info.is_dir()]
    found = [(name, kind) for name, kind in found if kind and (tipo is None or kind == tipo)]
    kinds = [kind for _, kind in found]
    duplicated = sorted({kind for kind in kinds if kinds.count(kind) > 1})
    if duplicated:
        raise ValueError(f"El ZIP contiene más de un TXT del tipo {', '.join(duplicated)}")
    return sorted(found, key=lambda pair: TIPOS.index(pair[1]))


def read_member(archive, member, tipo, *, on_batch=None, batch_size=1000):
    """Validate every line; emit bounded batches only when on_batch is supplied."""
    with archive.open(member) as stream:
        periodo = detect_period(stream, tipo)
    mapper = MAPPERS[tipo]
    key_fields = KEY_FIELDS[tipo]
    seen = set()
    summary = Counter()
    batch = []
    with archive.open(member) as stream:
        for line_number, fields in iter_fields(stream):
            try:
                data = mapper(fields, periodo)
            except ValueError as exc:
                raise ValueError(f"{member}, línea {line_number}: {exc}") from exc
            key = tuple(data[field] for field in key_fields)
            if key in seen:
                raise ValueError(f"{member}, línea {line_number}: clave duplicada {key}")
            seen.add(key)
            summary["filas"] += 1
            summary["incompletas"] += int(data.get("registro_incompleto", False))
            if on_batch is not None:
                batch.append(data)
                if len(batch) >= batch_size:
                    on_batch(batch)
                    batch = []
    if batch:
        on_batch(batch)
    summary["dus"] = len({key[0] for key in seen})
    return periodo, summary


def _orphans(tipo, periodo):
    """DUS referenced by bultos/documentos with no item in the base file of the same period."""
    if tipo == "EXP_BASE":
        return 0
    base = Exportacion.objects.filter(periodo_anio=periodo[0], periodo_mes=periodo[1]).values("numero_ident")
    rows = MODELS[tipo].objects.filter(periodo_anio=periodo[0], periodo_mes=periodo[1])
    return rows.exclude(numero_ident__in=base).values("numero_ident").distinct().count()


def load_member(archive, member, tipo, *, archivo_path, source=None, replace=False, batch_size=1000, log=None):
    """Load one TXT atomically. `source` reuses an ArchivoCarga created by the web upload."""
    log = log or (lambda message: None)
    model = MODELS[tipo]
    crc = archive.getinfo(member).CRC
    with archive.open(member) as stream:
        periodo = detect_period(stream, tipo)
    nombre = f"DUS:{tipo}:{periodo[0]}{periodo[1]:02d}:{crc:08x}"
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_BASE[tipo] + periodo[0] * 100 + periodo[1]])
        existing = model.objects.filter(periodo_anio=periodo[0], periodo_mes=periodo[1])
        previous = ArchivoCarga.objects.filter(tipo_archivo=tipo, periodo_anio=periodo[0], periodo_mes=periodo[1])
        if source is not None:
            previous = previous.exclude(pk=source.pk)
        loaded_before = previous.filter(estado="PROCESADO", observacion__contains=nombre).first()
        if loaded_before and not replace and existing.filter(archivo_origen=loaded_before).count() == loaded_before.total_ok == existing.count():
            log(f"{member}: ya cargado ({loaded_before.total_ok} filas), se omite.")
            if source is not None:
                source.estado = "PROCESADO"
                source.periodo_anio, source.periodo_mes = periodo
                source.observacion = f"{nombre} | Ya cargado previamente en la carga #{loaded_before.pk}; no se duplicó."
                source.save(update_fields=["estado", "periodo_anio", "periodo_mes", "observacion"])
            return periodo, Counter(filas=loaded_before.total_ok, ya_cargado=1)
        if existing.exists():
            if not replace:
                raise ValueError(
                    f"Ya existen {existing.count()} registros {tipo} de {periodo[1]:02d}/{periodo[0]}; "
                    "use --replace para reemplazarlos"
                )
            deleted = existing.delete()[0]
            log(f"{member}: reemplazados {deleted} registros previos de {periodo[1]:02d}/{periodo[0]}")
        previous.exclude(estado="PROCESANDO").update(estado="ERROR", observacion="Reemplazada por una carga posterior del mismo período")

        if source is None:
            source = ArchivoCarga(nombre_archivo=member.rsplit("/", 1)[-1], archivo=archivo_path, tipo_archivo=tipo)
        source.estado = "PROCESANDO"
        source.periodo_anio, source.periodo_mes = periodo
        source.total_registros = source.total_procesados = source.total_ok = source.total_error = 0
        source.observacion = f"{nombre} | Fuente TXT DUS: {member}"
        source.save()
        loaded = 0

        def insert_batch(batch):
            nonlocal loaded
            model.objects.bulk_create((model(archivo_origen=source, **data) for data in batch), batch_size=batch_size)
            loaded += len(batch)
            if loaded % 10000 < len(batch):
                log(f"{member}: {loaded} filas")

        _, summary = read_member(archive, member, tipo, on_batch=insert_batch, batch_size=batch_size)
        if loaded != summary["filas"] or existing.count() != loaded:
            raise ValueError(f"Conciliación fallida en {member}: {loaded} insertadas de {summary['filas']} leídas")
        summary["dus_sin_base"] = _orphans(tipo, periodo)
        source.estado = "PROCESADO"
        source.total_registros = source.total_procesados = source.total_ok = loaded
        source.observacion += (
            f" | {loaded} filas, {summary['dus']} DUS, {summary['incompletas']} filas truncadas en origen"
            + (f", {summary['dus_sin_base']} DUS sin ítems en el archivo base" if tipo != "EXP_BASE" else "")
        )
        source.save(update_fields=["estado", "total_registros", "total_procesados", "total_ok", "observacion"])
        return periodo, summary

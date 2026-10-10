from comercio.busqueda import texto_producto_importacion
from comercio.models import ArchivoCarga, ArchivoCargaStaging, Importacion


def split_semicolon_line(line: str) -> list[str]:
    return [part.strip() for part in line.rstrip("\n\r").split(";")]


def parse_txt_line(tipo_archivo: str, line: str) -> dict:
    parts = split_semicolon_line(line)
    if not parts:
        return {"raw_columns": []}

    def pick(*indexes: int) -> str:
        for index in indexes:
            if 0 <= index < len(parts):
                value = parts[index].strip()
                if value:
                    return value
        return ""

    if tipo_archivo == "IMP":
        # Positions are zero-based and follow doc-req/import/descripcion-y-estructura-de-datos-din.xlsx.
        numero_ident = pick(6)
        item = pick(1)
        fecha = pick(4)
        aduana_codigo = pick(2)
        comuna_importador_codigo = pick(5)
        via_transporte_codigo = pick(23)
        pais_origen_codigo = pick(21)

        partida_arancelaria = pick(157)
        glosa_mercancia = pick(133)
        valor_fob = pick(64)
        valor_flete = pick(67)
        valor_seguro = pick(70)
        valor_cif = pick(72)
        return {
            "numero_ident": numero_ident,
            "item": item,
            "fecha": fecha,
            "aduana_codigo": aduana_codigo,
            "comuna_importador_codigo": comuna_importador_codigo,
            "regimen_codigo": parts[28] if len(parts) > 28 else "",
            "pais_origen_codigo": pais_origen_codigo,
            "partida_arancelaria_codigo": partida_arancelaria,
            "glosa_mercancia": glosa_mercancia,
            "via_transporte_codigo": via_transporte_codigo,
            "valor_fob": valor_fob,
            "valor_flete": valor_flete,
            "valor_seguro": valor_seguro,
            "valor_cif": valor_cif,
            "raw_columns": parts,
        }

    return {"raw_columns": parts}


def normalize_rut(value: str) -> str:
    return "".join(char for char in str(value).upper() if char.isalnum())


def importers_by_key() -> dict:
    """ImportadorProbable by RUT+DV; sector reports also list the DIN NUM_UNICO_IMPORTADOR here (empty DV)."""
    from reportes.models import ImportadorProbable

    importers = {}
    for importer in ImportadorProbable.objects.all():
        key = normalize_rut(f"{importer.rut}{importer.dv}")
        if key and key not in importers:
            importers[key] = importer
    return importers


def store_staging_rows(archivo_carga: ArchivoCarga, txt_content: str) -> int:
    ArchivoCargaStaging.objects.filter(archivo_carga=archivo_carga).delete()
    created = 0
    for nro_linea, line in enumerate(txt_content.splitlines(), start=1):
        raw_line = line.strip()
        if not raw_line or raw_line.startswith("00;") or raw_line.count(";") < 20:
            continue
        parsed = parse_txt_line(archivo_carga.tipo_archivo, raw_line)
        ArchivoCargaStaging.objects.create(
            archivo_carga=archivo_carga,
            nro_linea=nro_linea,
            raw_line=raw_line,
            data_json=parsed,
            procesado=bool(parsed.get("raw_columns")),
            error="",
        )
        created += 1
        if created % 1000 == 0:
            ArchivoCarga.objects.filter(id=archivo_carga.id).update(total_procesados=created, estado="PROCESANDO")
    ArchivoCarga.objects.filter(id=archivo_carga.id).update(total_procesados=created, estado="PROCESANDO")
    return created


def materialize_final_rows(archivo_carga: ArchivoCarga) -> None:
    staging_rows = ArchivoCargaStaging.objects.filter(archivo_carga=archivo_carga, procesado=True).order_by("nro_linea")

    if archivo_carga.tipo_archivo == "IMP":
        importers = importers_by_key()
        Importacion.objects.filter(archivo_origen=archivo_carga).delete()
        buffer = []
        batch_size = 1000
        total = 0
        processed = 0
        ArchivoCarga.objects.filter(id=archivo_carga.id).update(
            estado="PROCESANDO",
            total_procesados=0,
            total_ok=0,
            total_error=0,
            observacion=(archivo_carga.observacion + " | ").strip(" |") + "Materialización de importaciones iniciada",
        )
        # iterator avoids caching hundreds of thousands of staging objects in a Celery worker.
        for row in staging_rows.iterator(chunk_size=batch_size):
            data = row.data_json
            numero_ident = data.get("numero_ident", "")
            buffer.append(Importacion(
                archivo_origen=archivo_carga,
                periodo_anio=archivo_carga.periodo_anio,
                periodo_mes=archivo_carga.periodo_mes,
                numero_ident=numero_ident,
                importador_probable_sugerido=importers.get(normalize_rut(numero_ident)),
                item=data.get("item", ""),
                fecha_text=data.get("fecha", ""),
                aduana_codigo=data.get("aduana_codigo", ""),
                comuna_importador_codigo=data.get("comuna_importador_codigo", ""),
                pais_origen_codigo=data.get("pais_origen_codigo", ""),
                via_transporte_codigo=data.get("via_transporte_codigo", ""),
                partida_arancelaria_codigo=data.get("partida_arancelaria_codigo", ""),
                glosa_mercancia=data.get("glosa_mercancia", ""),
                valor_fob=data.get("valor_fob", ""),
                valor_flete=data.get("valor_flete", ""),
                valor_seguro=data.get("valor_seguro", ""),
                valor_cif=data.get("valor_cif", ""),
                texto_producto=texto_producto_importacion(data),
                payload_json=data,
            ))
            processed += 1
            if len(buffer) >= batch_size:
                Importacion.objects.bulk_create(buffer, batch_size=batch_size)
                total += len(buffer)
                ArchivoCarga.objects.filter(id=archivo_carga.id).update(
                    total_ok=total,
                    total_registros=total,
                    total_procesados=processed,
                    observacion=(archivo_carga.observacion + " | ").strip(" |") + f"Materializando importaciones: {processed}/{staging_rows.count()}",
                )
                buffer.clear()
        if buffer:
            Importacion.objects.bulk_create(buffer, batch_size=batch_size)
            total += len(buffer)
            ArchivoCarga.objects.filter(id=archivo_carga.id).update(
                total_ok=total,
                total_registros=total,
                total_procesados=processed,
                observacion=(archivo_carga.observacion + " | ").strip(" |") + f"Materializando importaciones: {processed}/{staging_rows.count()}",
            )

from comercio.models import ArchivoCarga, ArchivoCargaStaging, Exportacion, ExportacionBulto, ExportacionDocTransporte, Importacion


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
        numero_ident = pick(0)
        item = pick(1)
        fecha = pick(4)
        aduana_codigo = pick(2)
        comuna_importador_codigo = pick(5)
        via_transporte_codigo = pick(57)
        pais_origen_codigo = pick(54)

        # Tabla fina por posición observada en la línea real:
        # 133..137 -> glosa / descripción
        # 145       -> tasa o coeficiente
        # 146       -> partida arancelaria principal
        # 147..150  -> códigos/cantidades auxiliares
        # 157       -> segunda aparición de partida arancelaria
        # 159       -> valor FOB observado
        # 161       -> valor flete observado
        # 163       -> valor seguro observado
        # 165       -> valor CIF observado
        partida_arancelaria = pick(146, 157)
        glosa_mercancia = pick(133, 134, 135, 136, 137)
        valor_fob = pick(159)
        valor_flete = pick(161)
        valor_seguro = pick(163)
        valor_cif = pick(165)
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

    if tipo_archivo == "EXP_BASE":
        partida_idx = 136 if len(parts) > 136 else None
        glosa_idx = 137 if len(parts) > 137 else None
        valor_fob_idx = 145 if len(parts) > 145 else None
        return {
            "numero_ident": parts[0] if len(parts) > 0 else "",
            "item": parts[1] if len(parts) > 1 else "",
            "fecha": parts[4] if len(parts) > 4 else "",
            "aduana_codigo": parts[5] if len(parts) > 5 else "",
            "pais_destino_codigo": parts[54] if len(parts) > 54 else "",
            "partida_arancelaria_codigo": parts[partida_idx] if partida_idx is not None else "",
            "glosa_mercancia": parts[glosa_idx] if glosa_idx is not None else "",
            "via_transporte_codigo": parts[57] if len(parts) > 57 else "",
            "valor_fob": parts[valor_fob_idx] if valor_fob_idx is not None else "",
            "raw_columns": parts,
        }

    if tipo_archivo == "EXP_BULTO":
        return {
            "numero_ident": parts[0] if len(parts) > 0 else "",
            "secuencia": parts[1] if len(parts) > 1 else "",
            "tipo_bulto_codigo": parts[2] if len(parts) > 2 else "",
            "cantidad_bultos": parts[3] if len(parts) > 3 else "",
            "marcas": parts[4] if len(parts) > 4 else "",
            "raw_columns": parts,
        }

    if tipo_archivo == "EXP_DOC":
        return {
            "numero_ident": parts[0] if len(parts) > 0 else "",
            "secuencia": parts[1] if len(parts) > 1 else "",
            "numero_documento": parts[2] if len(parts) > 2 else "",
            "fecha_documento_text": parts[3] if len(parts) > 3 else "",
            "nave": parts[4] if len(parts) > 4 else "",
            "numero_viaje": parts[5] if len(parts) > 5 else "",
            "puerto_embarque_codigo": parts[6] if len(parts) > 6 else "",
            "via_transporte_codigo": parts[7] if len(parts) > 7 else "",
            "raw_columns": parts,
        }

    return {"raw_columns": parts}


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
        from reportes.models import ImportadorProbable

        def normalize_rut(value: str) -> str:
            return "".join(char for char in str(value).upper() if char.isalnum())

        importers = {}
        for importer in ImportadorProbable.objects.all():
            key = normalize_rut(f"{importer.rut}{importer.dv}")
            if key and key not in importers:
                importers[key] = importer
        Importacion.objects.filter(archivo_origen=archivo_carga).delete()
        buffer = []
        batch_size = 5000
        total = 0
        processed = 0
        ArchivoCarga.objects.filter(id=archivo_carga.id).update(
            estado="PROCESANDO",
            total_procesados=0,
            total_ok=0,
            total_error=0,
            observacion=(archivo_carga.observacion + " | ").strip(" |") + "Materialización de importaciones iniciada",
        )
        for row in staging_rows:
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
    elif archivo_carga.tipo_archivo == "EXP_BASE":
        Exportacion.objects.filter(archivo_origen=archivo_carga).delete()
    elif archivo_carga.tipo_archivo == "EXP_BULTO":
        ExportacionBulto.objects.filter(archivo_origen=archivo_carga).delete()
    elif archivo_carga.tipo_archivo == "EXP_DOC":
        ExportacionDocTransporte.objects.filter(archivo_origen=archivo_carga).delete()

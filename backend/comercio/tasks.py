from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

from comercio.models import ArchivoCarga
from comercio.processing import materialize_final_rows, store_staging_rows


@shared_task
def process_uploaded_archive(archivo_carga_id: int, txt_content: str) -> None:
    archivo_carga = ArchivoCarga.objects.get(id=archivo_carga_id)
    total_ok = store_staging_rows(archivo_carga, txt_content)
    materialize_final_rows(archivo_carga)
    archivo_carga.total_registros = total_ok
    archivo_carga.total_ok = total_ok
    archivo_carga.estado = "PROCESADO"
    archivo_carga.save(update_fields=["estado", "total_registros", "total_ok"])


@shared_task
def process_uploaded_archive_by_id(archivo_carga_id: int) -> None:
    try:
        archivo_carga = ArchivoCarga.objects.get(id=archivo_carga_id)
    except ObjectDoesNotExist:
        return
    archivo_carga.estado = "PROCESANDO"
    archivo_carga.save(update_fields=["estado"])
    from zipfile import ZipFile

    with ZipFile(archivo_carga.archivo.path) as zf:
        txt_files = [name for name in zf.namelist() if name.lower().endswith(".txt")]
        if not txt_files:
            archivo_carga.estado = "ERROR"
            archivo_carga.save(update_fields=["estado"])
            return
        with zf.open(txt_files[0]) as txt_handle:
            content = txt_handle.read().decode("latin-1", errors="ignore")
    total_ok = store_staging_rows(archivo_carga, content)
    archivo_carga.observacion = (archivo_carga.observacion + " | ").strip(" |") + "Staging completado, iniciando materialización final"
    archivo_carga.save(update_fields=["observacion"])
    materialize_final_rows(archivo_carga)
    archivo_carga.total_registros = total_ok
    archivo_carga.total_procesados = total_ok
    archivo_carga.total_ok = total_ok
    archivo_carga.estado = "PROCESADO"
    archivo_carga.observacion = (archivo_carga.observacion + " | ").strip(" |") + "Materialización finalizada"
    archivo_carga.save(update_fields=["estado", "total_registros", "total_procesados", "total_ok", "observacion"])


@shared_task
def process_export_archive(archivo_carga_id: int) -> None:
    """Load the DUS TXT matching the upload's tipo_archivo through the streaming export loader."""
    from zipfile import BadZipFile, ZipFile

    from comercio.export_loader import export_members, load_member

    try:
        archivo_carga = ArchivoCarga.objects.get(id=archivo_carga_id)
    except ObjectDoesNotExist:
        return
    try:
        with ZipFile(archivo_carga.archivo.path) as archive:
            members = export_members(archive, archivo_carga.tipo_archivo)
            if not members:
                raise ValueError(f"El ZIP no contiene un TXT de {archivo_carga.get_tipo_archivo_display()}")
            member, tipo = members[0]
            load_member(archive, member, tipo, archivo_path=archivo_carga.archivo.name, source=archivo_carga)
    except (OSError, ValueError, BadZipFile) as exc:
        ArchivoCarga.objects.filter(id=archivo_carga_id).update(estado="ERROR", observacion=str(exc)[:2000])

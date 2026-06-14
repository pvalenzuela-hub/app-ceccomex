from celery import shared_task

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
    archivo_carga = ArchivoCarga.objects.get(id=archivo_carga_id)
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
    materialize_final_rows(archivo_carga)
    archivo_carga.total_registros = total_ok
    archivo_carga.total_procesados = total_ok
    archivo_carga.total_ok = total_ok
    archivo_carga.estado = "PROCESADO"
    archivo_carga.save(update_fields=["estado", "total_registros", "total_procesados", "total_ok"])

import os
import time
from pathlib import Path

import xlsxwriter
from celery import shared_task
from django.conf import settings

from reportes.models import InformeExcel


EXCEL_MAX_ROWS = 1_048_575  # one row is the header
INFORMES_DIR = Path(settings.BASE_DIR) / "cargas" / "informes"  # Docker volume shared by backend and celery
RETENCION_SEGUNDOS = 2 * 24 * 3600


def informe_path(informe):
    return INFORMES_DIR / f"informe_{informe.id}.xlsx"


def _purge_old_files():
    limit = time.time() - RETENCION_SEGUNDOS
    for path in INFORMES_DIR.glob("informe_*.xlsx*"):
        if path.stat().st_mtime < limit:
            path.unlink(missing_ok=True)


@shared_task
def generar_informe_importaciones(informe_id: int) -> None:
    from reportes.views import informe_importaciones_rows

    informe = InformeExcel.objects.filter(id=informe_id).first()
    if not informe:
        return
    INFORMES_DIR.mkdir(parents=True, exist_ok=True)
    _purge_old_files()
    partial = informe_path(informe).with_suffix(".xlsx.part")
    try:
        header, qs, values = informe_importaciones_rows(informe.parametros_json)
        total = qs.count()
        InformeExcel.objects.filter(id=informe_id).update(estado="PROCESANDO", filas_total=total)
        if total > EXCEL_MAX_ROWS:
            raise ValueError(
                f"El informe tiene {total:,} filas y Excel admite {EXCEL_MAX_ROWS:,}. Acote el período o agregue filtros.".replace(",", ".")
            )
        workbook = xlsxwriter.Workbook(str(partial), {"constant_memory": True, "strings_to_numbers": False})
        sheet = workbook.add_worksheet("Importaciones")
        sheet.write_row(0, 0, header)
        for number, row in enumerate(qs.iterator(chunk_size=2000), start=1):
            sheet.write_row(number, 0, values(row))
            if number % 10000 == 0:
                InformeExcel.objects.filter(id=informe_id).update(filas_procesadas=number)
        workbook.close()
        os.replace(partial, informe_path(informe))
        InformeExcel.objects.filter(id=informe_id).update(estado="LISTO", filas_procesadas=total)
    except Exception as exc:  # The user sees the message; the worker must not leave the report "PROCESANDO".
        partial.unlink(missing_ok=True)
        InformeExcel.objects.filter(id=informe_id).update(estado="ERROR", error=str(exc)[:2000])
        if not isinstance(exc, ValueError):
            raise

import zipfile

from rest_framework import status
from rest_framework.decorators import api_view
from django.db.models import Count
from rest_framework.response import Response
from kombu.exceptions import OperationalError

from comercio.models import ArchivoCarga, ArchivoCargaStaging
from comercio.processing import materialize_final_rows, store_staging_rows
from comercio.tasks import process_uploaded_archive
from comercio.serializers import (
    ArchivoCargaListSerializer,
    ArchivoCargaSerializer,
    ArchivoCargaStagingSerializer,
)


@api_view(["POST"])
def upload_archivo(request):
    serializer = ArchivoCargaSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    archivo_carga = serializer.save()
    archivo_carga.estado = "PROCESANDO"
    archivo_carga.save(update_fields=["estado"])

    if not zipfile.is_zipfile(archivo_carga.archivo.path):
        archivo_carga.estado = "ERROR"
        archivo_carga.observacion = (archivo_carga.observacion + " | ").strip(" |") + "El archivo no es un ZIP válido."
        archivo_carga.save(update_fields=["estado", "observacion"])
        return Response({"detail": "El archivo no es un ZIP válido."}, status=status.HTTP_400_BAD_REQUEST)

    with zipfile.ZipFile(archivo_carga.archivo.path) as zf:
        txt_files = [name for name in zf.namelist() if name.lower().endswith(".txt")]
        archivo_carga.total_registros = 0
        archivo_carga.total_procesados = 0
        archivo_carga.total_ok = 0
        archivo_carga.total_error = 0
        if txt_files:
            archivo_carga.observacion = (archivo_carga.observacion + " | ").strip(" |") + f"TXT detectados: {', '.join(txt_files[:3])}"
            with zf.open(txt_files[0]) as txt_handle:
                content = txt_handle.read().decode("latin-1", errors="ignore")
                if len(content) > 500_000:
                    archivo_carga.estado = "PROCESANDO"
                    archivo_carga.observacion = (archivo_carga.observacion + " | ").strip(" |") + "Procesamiento en segundo plano"
                    archivo_carga.save(update_fields=["estado", "observacion"])
                    try:
                        from comercio.tasks import process_uploaded_archive_by_id
                        process_uploaded_archive_by_id.delay(archivo_carga.id)
                        return Response(ArchivoCargaSerializer(archivo_carga).data, status=status.HTTP_202_ACCEPTED)
                    except OperationalError:
                        archivo_carga.observacion = (archivo_carga.observacion + " | ").strip(" |") + "Fallo cola, procesando en forma síncrona"
                        archivo_carga.save(update_fields=["observacion"])
                        total_ok = store_staging_rows(archivo_carga, content)
                        archivo_carga.total_registros = total_ok
                        archivo_carga.total_procesados = total_ok
                        archivo_carga.total_ok = total_ok
                        materialize_final_rows(archivo_carga)
                        archivo_carga.estado = "PROCESADO"
                        archivo_carga.save(update_fields=["estado", "total_registros", "total_procesados", "total_ok"])
                        return Response(ArchivoCargaSerializer(archivo_carga).data, status=status.HTTP_201_CREATED)

                total_ok = store_staging_rows(archivo_carga, content)
                archivo_carga.total_registros = total_ok
                archivo_carga.total_procesados = total_ok
                archivo_carga.total_ok = total_ok
                materialize_final_rows(archivo_carga)

    archivo_carga.estado = "PROCESADO"
    archivo_carga.save(update_fields=["estado", "total_registros", "total_procesados", "total_ok", "total_error", "observacion"])
    return Response(ArchivoCargaSerializer(archivo_carga).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def list_archivos(request):
    qs = ArchivoCarga.objects.annotate(staging_count=Count("staging")).exclude(nombre_archivo__icontains="test-upload").order_by("-creado")[:20]
    return Response(ArchivoCargaListSerializer(qs, many=True).data)


@api_view(["GET"])
def list_staging(request, archivo_id: int):
    qs = ArchivoCargaStaging.objects.filter(archivo_carga_id=archivo_id).order_by("nro_linea")[:100]
    return Response(ArchivoCargaStagingSerializer(qs, many=True).data)

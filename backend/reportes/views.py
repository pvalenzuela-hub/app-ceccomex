from rest_framework.decorators import api_view
from rest_framework.response import Response

from reportes.models import ImportadorProbable, ReporteSectorial, ReporteSectorialDetalle
from reportes.serializers import ImportadorProbableSerializer, ReporteSectorialDetalleSerializer, ReporteSectorialSerializer


@api_view(["GET"])
def reportes(request):
    return Response(ReporteSectorialSerializer(ReporteSectorial.objects.all(), many=True).data)


@api_view(["GET"])
def detalle_reporte(request, reporte_id: int):
    rows = ReporteSectorialDetalle.objects.filter(reporte_id=reporte_id).select_related("importador_probable")[:200]
    return Response(ReporteSectorialDetalleSerializer(rows, many=True).data)


@api_view(["GET"])
def importadores_probables(request):
    query = request.query_params.get("q", "")
    rows = ImportadorProbable.objects.all()
    if query:
        rows = rows.filter(nombre__icontains=query)
    return Response(ImportadorProbableSerializer(rows[:100], many=True).data)

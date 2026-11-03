from functools import lru_cache

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Q, TextField, Value
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Coalesce, Concat, LPad, Substr
from openpyxl import Workbook

from comercio.models import Importacion
from consultas.serializers import ImportacionConsultaSerializer
from consultas.serializers import ConsultaGuardadaSerializer
from consultas.resolvers import resolve_catalogo
from consultas.resolvers import pendientes_importaciones
from consultas.models import ConsultaGuardada
from catalogos.models import PartidaArancelaria
from reportes.views import DIN_POSITIONS, codigo_din_sql


def _fecha_aceptacion_iso():
    """FECACEP as YYYY-MM-DD, to compare with the date filters; the DIN keeps DDMMYYYY, without the leading zero in MDB."""
    fecha = LPad(Coalesce(KeyTextTransform("FEC_ACE", KeyTransform("legacy_fields", "payload_json")), KeyTextTransform(str(DIN_POSITIONS["FECACEP"]), KeyTransform("raw_columns", "payload_json"))), 8, Value("0"))
    return Concat(Substr(fecha, 5, 4), Value("-"), Substr(fecha, 3, 2), Value("-"), Substr(fecha, 1, 2), output_field=TextField())


def _importaciones_filtradas(params):
    qs = Importacion.objects.select_related("archivo_origen", "importador_probable_sugerido").order_by("-creado", "-id")
    for field, value in (
        ("numero_ident", params.get("numero_ident")),
        ("aduana_codigo", params.get("aduana_codigo")),
        ("comuna_importador_codigo", params.get("comuna_importador_codigo")),
        ("partida_arancelaria_codigo", params.get("partida_arancelaria_codigo")),
        ("pais_origen_codigo", params.get("pais_origen_codigo")),
    ):
        if value:
            qs = qs.alias(**{f"_{field}": codigo_din_sql(field)}).filter(**{f"_{field}__icontains": value})
    if params.get("periodo_anio"):
        qs = qs.filter(periodo_anio=params.get("periodo_anio"))
    if params.get("periodo_mes"):
        qs = qs.filter(periodo_mes=params.get("periodo_mes"))
    if params.get("periodo_mes_desde"):
        qs = qs.filter(periodo_mes__gte=params.get("periodo_mes_desde"))
    if params.get("periodo_mes_hasta"):
        qs = qs.filter(periodo_mes__lte=params.get("periodo_mes_hasta"))
    partida_busqueda = params.get("partida_busqueda")
    if partida_busqueda:
        codes = PartidaArancelaria.objects.filter(Q(codigo__icontains=partida_busqueda) | Q(glosa__icontains=partida_busqueda)).values_list("codigo", flat=True)
        qs = qs.alias(_partida=codigo_din_sql("partida_arancelaria_codigo")).filter(_partida__in=codes)
    if params.get("fecha_desde") or params.get("fecha_hasta"):
        qs = qs.alias(_fecha=_fecha_aceptacion_iso())
    if params.get("fecha_desde"):
        qs = qs.filter(_fecha__gte=params.get("fecha_desde"))
    if params.get("fecha_hasta"):
        qs = qs.filter(_fecha__lte=params.get("fecha_hasta"))
    return qs


@api_view(["GET"])
def importaciones(request):
    qs = _importaciones_filtradas(request.query_params)
    page = max(int(request.query_params.get("page", "1") or "1"), 1)
    page_size = min(max(int(request.query_params.get("page_size", "50") or "50"), 1), 100)
    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    return Response({
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": ImportacionConsultaSerializer(qs[start:end], many=True, context={"resolver": resolve_catalogo}).data,
    })


@api_view(["GET"])
def pendientes_revision(request):
    limit = max(min(int(request.query_params.get("limit", "100") or "100"), 500), 1)
    return Response({"results": pendientes_importaciones(limit=limit)})


@api_view(["GET", "POST"])
def favoritos(request):
    if request.method == "GET":
        return Response(ConsultaGuardadaSerializer(ConsultaGuardada.objects.order_by("-creado"), many=True).data)
    serializer = ConsultaGuardadaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(ConsultaGuardadaSerializer(serializer.save()).data, status=201)


@api_view(["DELETE"])
def favorito_detalle(request, favorito_id: int):
    ConsultaGuardada.objects.filter(id=favorito_id).delete()
    return Response(status=204)


@api_view(["GET"])
def exportar_importaciones(request):
    qs = _importaciones_filtradas(request.query_params)

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(title="Consultas")
    sheet.append([
        "numero_ident",
        "item",
        "fecha_text",
        "aduana_codigo",
        "aduana_glosa",
        "comuna_importador_codigo",
        "comuna_importador_glosa",
        "pais_origen_codigo",
        "pais_origen_glosa",
        "partida_arancelaria_codigo",
        "partida_glosa",
        "glosa_mercancia",
        "valor_fob",
        "valor_flete",
        "valor_seguro",
        "valor_cif",
        "creado",
    ])

    resolver = lru_cache(maxsize=None)(resolve_catalogo)
    for item in qs:
        fila = ImportacionConsultaSerializer(context={"resolver": resolver}).to_representation(item)
        sheet.append([
            fila["numero_ident"],
            fila["item"],
            fila["fecha_text"],
            fila["aduana_codigo"],
            fila["aduana"].get("glosa", ""),
            fila["comuna_importador_codigo"],
            fila["comuna_importador"].get("glosa", ""),
            fila["pais_origen_codigo"],
            fila["pais_origen"].get("glosa", ""),
            fila["partida_arancelaria_codigo"],
            fila["partida"].get("glosa", ""),
            fila["glosa_mercancia"],
            fila["valor_fob"],
            fila["valor_flete"],
            fila["valor_seguro"],
            fila["valor_cif"],
            item.creado.isoformat(),
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="consultas_importaciones.xlsx"'
    workbook.save(response)
    return response

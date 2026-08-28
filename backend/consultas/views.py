from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponse
from openpyxl import Workbook

from comercio.models import Importacion
from consultas.serializers import ImportacionConsultaSerializer
from consultas.resolvers import resolve_catalogo
from consultas.resolvers import pendientes_importaciones


@api_view(["GET"])
def importaciones(request):
    qs = Importacion.objects.select_related("archivo_origen").order_by("-creado")
    numero_ident = request.query_params.get("numero_ident")
    periodo_anio = request.query_params.get("periodo_anio")
    periodo_mes = request.query_params.get("periodo_mes")
    aduana_codigo = request.query_params.get("aduana_codigo")
    partida_arancelaria_codigo = request.query_params.get("partida_arancelaria_codigo")
    pais_origen_codigo = request.query_params.get("pais_origen_codigo")
    fecha_desde = request.query_params.get("fecha_desde")
    fecha_hasta = request.query_params.get("fecha_hasta")
    page = max(int(request.query_params.get("page", "1") or "1"), 1)
    page_size = min(max(int(request.query_params.get("page_size", "50") or "50"), 1), 100)
    if numero_ident:
        qs = qs.filter(numero_ident__icontains=numero_ident)
    if periodo_anio:
        qs = qs.filter(periodo_anio=periodo_anio)
    if periodo_mes:
        qs = qs.filter(periodo_mes=periodo_mes)
    if aduana_codigo:
        qs = qs.filter(aduana_codigo__icontains=aduana_codigo)
    if request.query_params.get("comuna_importador_codigo"):
        qs = qs.filter(comuna_importador_codigo__icontains=request.query_params.get("comuna_importador_codigo"))
    if partida_arancelaria_codigo:
        qs = qs.filter(partida_arancelaria_codigo__icontains=partida_arancelaria_codigo)
    if pais_origen_codigo:
        qs = qs.filter(pais_origen_codigo__icontains=pais_origen_codigo)
    if fecha_desde:
        qs = qs.filter(fecha_text__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_text__lte=fecha_hasta)
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


@api_view(["GET"])
def exportar_importaciones(request):
    qs = Importacion.objects.select_related("archivo_origen").order_by("-creado")
    numero_ident = request.query_params.get("numero_ident")
    periodo_anio = request.query_params.get("periodo_anio")
    periodo_mes = request.query_params.get("periodo_mes")
    aduana_codigo = request.query_params.get("aduana_codigo")
    partida_arancelaria_codigo = request.query_params.get("partida_arancelaria_codigo")
    pais_origen_codigo = request.query_params.get("pais_origen_codigo")
    fecha_desde = request.query_params.get("fecha_desde")
    fecha_hasta = request.query_params.get("fecha_hasta")

    if numero_ident:
        qs = qs.filter(numero_ident__icontains=numero_ident)
    if periodo_anio:
        qs = qs.filter(periodo_anio=periodo_anio)
    if periodo_mes:
        qs = qs.filter(periodo_mes=periodo_mes)
    if aduana_codigo:
        qs = qs.filter(aduana_codigo__icontains=aduana_codigo)
    if request.query_params.get("comuna_importador_codigo"):
        qs = qs.filter(comuna_importador_codigo__icontains=request.query_params.get("comuna_importador_codigo"))
    if partida_arancelaria_codigo:
        qs = qs.filter(partida_arancelaria_codigo__icontains=partida_arancelaria_codigo)
    if pais_origen_codigo:
        qs = qs.filter(pais_origen_codigo__icontains=pais_origen_codigo)
    if fecha_desde:
        qs = qs.filter(fecha_text__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_text__lte=fecha_hasta)

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

    resolver = resolve_catalogo
    for item in qs:
        aduana = resolver("aduanas", item.aduana_codigo)
        comuna = resolver("comunas", item.comuna_importador_codigo)
        pais = resolver("paises", item.pais_origen_codigo)
        partida = resolver("partidas", item.partida_arancelaria_codigo)
        sheet.append([
            item.numero_ident,
            item.item,
            item.fecha_text,
            item.aduana_codigo,
            aduana.get("glosa", ""),
            item.comuna_importador_codigo,
            comuna.get("glosa", ""),
            item.pais_origen_codigo,
            pais.get("glosa", ""),
            item.partida_arancelaria_codigo,
            partida.get("glosa", ""),
            item.glosa_mercancia,
            item.valor_fob,
            item.valor_flete,
            item.valor_seguro,
            item.valor_cif,
            item.creado.isoformat(),
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="consultas_importaciones.xlsx"'
    workbook.save(response)
    return response

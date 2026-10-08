"""Paged search and Excel download over DUS export items."""

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from catalogos.models import PartidaArancelaria
from comercio.models import Exportacion, ExportacionBulto, ExportacionDocTransporte
from reportes.exportaciones import CATALOG_FIELDS, EXPORT_COLUMN_MAP, export_column_value, glosa, load_catalogs, xlsx_response


TEXT_FILTERS = {
    "numero_ident": "numero_ident",
    "exportador_codigo": "exportador_codigo",
    "aduana_codigo": "aduana_codigo",
    "pais_destino_codigo": "pais_destino_codigo",
    "puerto_embarque_codigo": "puerto_embarque_codigo",
    "via_transporte_codigo": "via_transporte_codigo",
}
EXCEL_COLUMNS = [
    "numero_ident", "item", "fecha_text", "exportador_codigo", "aduana_codigo", "aduana_glosa",
    "pais_destino_codigo", "pais_destino_glosa", "puerto_embarque_codigo", "puerto_embarque_glosa",
    "puerto_desembarque_codigo", "puerto_desembarque_glosa", "via_transporte_codigo", "via_transporte_glosa",
    "partida_arancelaria_codigo", "partida_glosa", "glosa_mercancia", "unidad_medida_glosa", "cantidad_mercancia",
    "valor_fob_unitario", "valor_fob", "peso_bruto_item", "valor_fob_dus", "valor_cif_dus",
]


def _int_param(params, name):
    value = (params.get(name) or "").strip()
    return int(value) if value.isdigit() else None


def filtered_exportaciones(params):
    qs = Exportacion.objects.order_by("-id")
    for param, field in TEXT_FILTERS.items():
        value = (params.get(param) or "").strip()
        if value:
            # Codes are exact; the DUS number accepts partial input.
            qs = qs.filter(**{f"{field}__icontains" if param == "numero_ident" else field: value})
    for param, lookup in (("periodo_anio", "periodo_anio"), ("periodo_mes", "periodo_mes"), ("periodo_mes_desde", "periodo_mes__gte"), ("periodo_mes_hasta", "periodo_mes__lte")):
        value = _int_param(params, param)
        if value is not None:
            qs = qs.filter(**{lookup: value})
    if params.get("fecha_desde"):
        qs = qs.filter(fecha_text__gte=params["fecha_desde"])
    if params.get("fecha_hasta"):
        qs = qs.filter(fecha_text__lte=params["fecha_hasta"])
    partida = (params.get("partida_busqueda") or "").strip()
    if partida:
        codes = PartidaArancelaria.objects.filter(Q(codigo__icontains=partida) | Q(glosa__icontains=partida)).values_list("codigo", flat=True)
        qs = qs.filter(Q(partida_arancelaria_codigo__startswith=partida) | Q(partida_arancelaria_codigo__in=codes))
    mercancia = (params.get("mercancia") or "").strip()
    if mercancia:
        qs = qs.filter(glosa_mercancia__icontains=mercancia)
    return qs


def _row(row, catalogs):
    data = {
        field: getattr(row, field)
        for field in (
            "id", "periodo_anio", "periodo_mes", "numero_ident", "item", "fecha_text", "exportador_codigo",
            "partida_arancelaria_codigo", "glosa_mercancia", "unidad_medida_codigo", "cantidad_mercancia",
            "valor_fob_unitario", "valor_fob", "peso_bruto_item", "valor_fob_dus", "valor_cif_dus", "registro_incompleto",
        )
    }
    for name, (field, grupo) in CATALOG_FIELDS.items():
        data[field] = getattr(row, field)
        data[f"{name}_glosa"] = glosa(catalogs, grupo, getattr(row, field))
    data["partida_glosa"] = glosa(catalogs, "partidas", row.partida_arancelaria_codigo)
    return data


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exportaciones(request):
    qs = filtered_exportaciones(request.query_params)
    page = max(_int_param(request.query_params, "page") or 1, 1)
    page_size = min(max(_int_param(request.query_params, "page_size") or 50, 1), 100)
    start = (page - 1) * page_size
    catalogs = load_catalogs()
    return Response({
        "count": qs.count(),
        "page": page,
        "page_size": page_size,
        "results": [_row(row, catalogs) for row in qs[start:start + page_size]],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exportacion_detalle(request, numero_ident: str):
    """All items, bultos and transport documents of one DUS."""
    items = Exportacion.objects.filter(numero_ident=numero_ident).order_by("periodo_anio", "periodo_mes", "id")
    if not items.exists():
        return Response({"detail": "DUS no encontrado."}, status=404)
    catalogs = load_catalogs()
    first = items.first()
    filtros = {"numero_ident": numero_ident, "periodo_anio": first.periodo_anio, "periodo_mes": first.periodo_mes}
    return Response({
        "numero_ident": numero_ident,
        "dus": first.payload_json.get("dus_fields", {}),
        "items": [_row(row, catalogs) for row in items],
        "bultos": [
            {**bulto, "tipo_bulto_glosa": glosa(catalogs, "tipos_bulto", bulto["tipo_bulto_codigo"])}
            for bulto in ExportacionBulto.objects.filter(**filtros).order_by("id").values("secuencia", "tipo_bulto_codigo", "cantidad_bultos", "marcas")
        ],
        "documentos": list(ExportacionDocTransporte.objects.filter(**filtros).order_by("id").values("secuencia", "numero_documento", "fecha_documento_text", "nave", "numero_viaje")),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exportar_exportaciones(request):
    qs = filtered_exportaciones(request.query_params)
    catalogs = load_catalogs()
    return xlsx_response(
        "consultas_exportaciones.xlsx", "Consultas",
        [EXPORT_COLUMN_MAP[key] for key in EXCEL_COLUMNS],
        ([export_column_value(row, key, catalogs) for key in EXCEL_COLUMNS] for row in qs.iterator(chunk_size=2000)),
    )

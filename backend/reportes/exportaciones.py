"""Excel report builder for DUS exports (one row per DUS item)."""

import tempfile
from collections import defaultdict

import xlsxwriter
from django.db.models import Func, Q, TextField
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from comercio.dus_txt import DUS_COLUMNS
from comercio.models import Exportacion, ExportacionBulto, ExportacionDocTransporte
from reportes.views import _period_range_q, _without_accents, parse_periodo, solicitar_informe


# (field on Exportacion, catalog group) for every code that has a description.
CATALOG_FIELDS = {
    "aduana": ("aduana_codigo", "aduanas"),
    "comuna_exportador": ("comuna_exportador_codigo", "comunas"),
    "region_origen": ("region_origen_codigo", "regiones"),
    "puerto_embarque": ("puerto_embarque_codigo", "puertos"),
    "puerto_desembarque": ("puerto_desembarque_codigo", "puertos"),
    "pais_destino": ("pais_destino_codigo", "paises"),
    "via_transporte": ("via_transporte_codigo", "via_transporte"),
    "unidad_medida": ("unidad_medida_codigo", "unidades_medida"),
}
CATALOG_GROUPS = sorted({grupo for _, grupo in CATALOG_FIELDS.values()} | {"tipos_bulto"})

EXPORT_COLUMNS = [
    ("fecha_text", "Fecha"), ("dia", "Día"), ("mes", "Mes"), ("anio", "Año"),
    ("numero_ident", "Nº identificador DUS"), ("item", "Ítem"),
    ("exportador_codigo", "Exportador (Nº único anónimo)"),
    ("comuna_exportador_codigo", "Código comuna exportador"), ("comuna_exportador_glosa", "Comuna exportador"),
    ("region_origen_codigo", "Código región origen"), ("region_origen_glosa", "Región origen"),
    ("aduana_codigo", "Código aduana"), ("aduana_glosa", "Aduana"),
    ("pais_destino_codigo", "Código país destino"), ("pais_destino_glosa", "País destino"),
    ("puerto_embarque_codigo", "Código puerto embarque"), ("puerto_embarque_glosa", "Puerto embarque"),
    ("puerto_desembarque_codigo", "Código puerto desembarque"), ("puerto_desembarque_glosa", "Puerto desembarque"),
    ("via_transporte_codigo", "Código vía"), ("via_transporte_glosa", "Vía"),
    ("valor_fob", "US$ FOB ítem"), ("valor_fob_dus", "US$ FOB total DUS"),
    ("valor_flete_dus", "US$ flete DUS"), ("valor_seguro_dus", "US$ seguro DUS"), ("valor_cif_dus", "US$ CIF DUS"),
    ("unidad_medida_codigo", "Código unidad de medida"), ("unidad_medida_glosa", "Unidad de medida"),
    ("cantidad_mercancia", "Cantidad"), ("valor_fob_unitario", "US$ FOB unitario"),
    ("valor_liquido_retorno_dus", "Valor líquido retorno DUS"), ("peso_bruto_item", "Peso bruto ítem (kg)"),
    ("partida_arancelaria_codigo", "Arancel"), ("partida_glosa", "Descripción partida arancelaria"),
    ("glosa_mercancia", "Mercadería"),
    *[(f"dus:ATRIBUTO{number}", f"Variedad {number}") for number in range(1, 7)],
    *[
        (f"dus:{prefix}OBSERVACION{number}", f"{label} observación {number}")
        for number in range(1, 4)
        for prefix, label in (("CODIGO", "Código"), ("VALOR", "Valor"), ("GLOSA", "Glosa"))
    ],
    ("total_bultos", "Total bultos DUS (archivo bultos)"), ("tipos_bulto", "Tipos de bulto"),
    ("documentos_transporte", "Documentos de transporte"), ("naves", "Naves"), ("viajes", "Viajes"),
    ("registro_incompleto", "Registro truncado en origen"),
]
_NAMED = {key for key, _ in EXPORT_COLUMNS}
EXPORT_COLUMNS.extend((f"dus:{name}", f"DUS - {name}") for name in DUS_COLUMNS if f"dus:{name}" not in _NAMED)
EXPORT_COLUMN_MAP = dict(EXPORT_COLUMNS)
# Mirrors doc-req/CAMPOS DE SALIDA DE EXPORTACIÓN.xlsx; RUT/DV are anonymized in the DUS files.
DEFAULT_EXPORT_COLUMNS = [
    "fecha_text", "dia", "mes", "anio", "exportador_codigo", "comuna_exportador_codigo", "aduana_glosa",
    "pais_destino_glosa", "puerto_embarque_glosa", "puerto_desembarque_glosa", "via_transporte_glosa",
    "valor_fob", "valor_flete_dus", "valor_seguro_dus", "valor_cif_dus", "unidad_medida_glosa",
    "cantidad_mercancia", "valor_fob_unitario", "valor_liquido_retorno_dus",
    "dus:CODIGOOBSERVACION1", "dus:VALOROBSERVACION1", "dus:GLOSAOBSERVACION1",
    "partida_arancelaria_codigo", "partida_glosa", "glosa_mercancia", "dus:ATRIBUTO1", "dus:ATRIBUTO2", "dus:ATRIBUTO3",
]
FILTER_FIELDS = {
    "aduana_codigo": "aduanas", "pais_destino_codigo": "paises", "puerto_embarque_codigo": "puertos",
    "puerto_desembarque_codigo": "puertos", "via_transporte_codigo": "via_transporte", "region_origen_codigo": "regiones",
}
# Stored as dotted strings; written as numbers so they can be summed in Excel.
NUMERIC_COLUMNS = {
    "valor_fob", "valor_fob_dus", "valor_flete_dus", "valor_seguro_dus", "valor_cif_dus", "cantidad_mercancia",
    "valor_fob_unitario", "valor_liquido_retorno_dus", "peso_bruto_item",
}
BULTO_COLUMNS = {"total_bultos", "tipos_bulto"}
DOC_COLUMNS = {"documentos_transporte", "naves", "viajes"}


def xlsx_response(filename, sheet_name, header, rows):
    """Stream rows into a temporary .xlsx (constant memory); xlsxwriter is ~2x faster than openpyxl here."""
    handle = tempfile.TemporaryFile()
    workbook = xlsxwriter.Workbook(handle, {"constant_memory": True, "strings_to_numbers": False})
    sheet = workbook.add_worksheet(sheet_name)
    sheet.write_row(0, 0, header)
    for number, row in enumerate(rows, start=1):
        sheet.write_row(number, 0, row)
    workbook.close()
    handle.seek(0)
    return FileResponse(
        handle, as_attachment=True, filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def load_catalogs(groups=CATALOG_GROUPS):
    catalogs = {grupo: dict(CatalogoCodigo.objects.filter(grupo=grupo).values_list("codigo", "glosa")) for grupo in groups}
    catalogs["partidas"] = dict(PartidaArancelaria.objects.values_list("codigo", "glosa"))
    return catalogs


def glosa(catalogs, grupo, codigo):
    return catalogs.get(grupo, {}).get(str(codigo or ""), "")


def _selected_values(value):
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


PRODUCT_DUS_FIELDS = ("NOMBRE", "ATRIBUTO1", "ATRIBUTO2", "ATRIBUTO3", "ATRIBUTO4", "ATRIBUTO5", "ATRIBUTO6")


def _product_text():
    """Mercadería + variedades, concatenated without separators: DUS splits descriptions mid-word too."""
    fields = KeyTransform("dus_fields", "payload_json")
    return Func(*[KeyTextTransform(name, fields) for name in PRODUCT_DUS_FIELDS], function="CONCAT", output_field=TextField())


def filtered_exportaciones_informe(filters, periodo_anio=None, periodo_mes=None, desde=None, hasta=None):
    qs = Exportacion.objects.order_by("periodo_anio", "periodo_mes", "fecha_date", "numero_ident", "id")
    if desde and hasta:
        qs = qs.filter(_period_range_q(desde, hasta))
    if _int_or_none(periodo_anio):
        qs = qs.filter(periodo_anio=int(periodo_anio))
    if _int_or_none(periodo_mes):
        qs = qs.filter(periodo_mes=int(periodo_mes))
    for field in FILTER_FIELDS:
        values = _selected_values(filters.get(field, []))
        if values:
            qs = qs.filter(**{f"{field}__in": values})
    partidas = _selected_values(filters.get("partidas", []))
    if partidas:
        qs = qs.filter(partida_arancelaria_codigo__in=partidas)
    exportadores = _selected_values(filters.get("exportadores", []))
    if exportadores:
        qs = qs.filter(exportador_codigo__in=exportadores)
    productos = _selected_values(filters.get("productos", []))
    if productos:
        product_filter = Q()
        for term in productos:
            for variant in {term, _without_accents(term)}:
                product_filter |= Q(texto_producto__icontains=variant)
        qs = qs.annotate(texto_producto=_product_text()).filter(product_filter)
    return qs


def _in_range(model, desde, hasta):
    return model.objects.filter(_period_range_q(desde, hasta))


def _bultos_by_dus(desde, hasta, catalogs):
    """{(anio, mes, numero_ident): (total bultos, tipos)} for the report range."""
    totals = defaultdict(lambda: [0, set()])
    rows = _in_range(ExportacionBulto, desde, hasta).values_list("periodo_anio", "periodo_mes", "numero_ident", "cantidad_bultos", "tipo_bulto_codigo")
    for anio, mes, numero, cantidad, tipo in rows.iterator(chunk_size=5000):
        key = (anio, mes, numero)
        try:
            totals[key][0] += int(float(cantidad or 0))
        except ValueError:
            pass
        totals[key][1].add(glosa(catalogs, "tipos_bulto", tipo) or tipo)
    return {key: (total, ", ".join(sorted(tipos))) for key, (total, tipos) in totals.items()}


def _docs_by_dus(desde, hasta):
    docs = defaultdict(lambda: ([], [], []))
    rows = _in_range(ExportacionDocTransporte, desde, hasta).order_by("numero_ident", "secuencia")
    for anio, mes, numero, documento, nave, viaje in rows.values_list("periodo_anio", "periodo_mes", "numero_ident", "numero_documento", "nave", "numero_viaje").iterator(chunk_size=5000):
        for values, value in zip(docs[(anio, mes, numero)], (documento, nave, viaje)):
            if value and value not in values:
                values.append(value)
    return {key: tuple(" | ".join(values) for values in lists) for key, lists in docs.items()}


def export_column_value(row, key, catalogs, bultos=None, docs=None):
    if key.startswith("dus:"):
        return row.payload_json.get("dus_fields", {}).get(key[4:], "")
    if key.endswith("_glosa") and key[:-6] in CATALOG_FIELDS:
        field, grupo = CATALOG_FIELDS[key[:-6]]
        return glosa(catalogs, grupo, getattr(row, field))
    if key == "partida_glosa":
        return glosa(catalogs, "partidas", row.partida_arancelaria_codigo)
    if key in ("dia", "mes", "anio"):
        return getattr(row.fecha_date, {"dia": "day", "mes": "month", "anio": "year"}[key]) if row.fecha_date else ""
    if key == "registro_incompleto":
        return "Sí" if row.registro_incompleto else ""
    if key in BULTO_COLUMNS:
        total, tipos = (bultos or {}).get((row.periodo_anio, row.periodo_mes, row.numero_ident), ("", ""))
        return total if key == "total_bultos" else tipos
    if key in DOC_COLUMNS:
        values = (docs or {}).get((row.periodo_anio, row.periodo_mes, row.numero_ident), ("", "", ""))
        return values[("documentos_transporte", "naves", "viajes").index(key)]
    if key in NUMERIC_COLUMNS:
        value = getattr(row, key)
        return float(value) if value else ""
    return getattr(row, key, "")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exportaciones_configuracion(request):
    labels = {"aduana_codigo": "ADUANAS", "pais_destino_codigo": "PAISES", "puerto_embarque_codigo": "PUERTOS", "puerto_desembarque_codigo": "PUERTOS", "via_transporte_codigo": "VIAS_TRANSPORTE", "region_origen_codigo": "REGIONES"}
    catalogos = {
        labels[field]: list(CatalogoCodigo.objects.filter(grupo=grupo).values("codigo", "glosa").order_by("codigo"))
        for field, grupo in FILTER_FIELDS.items()
    }
    periodos = list(Exportacion.objects.values_list("periodo_anio", "periodo_mes").distinct().order_by("-periodo_anio", "-periodo_mes"))
    return Response({
        "columnas": [{"key": key, "label": label, "default": key in DEFAULT_EXPORT_COLUMNS} for key, label in EXPORT_COLUMNS],
        "catalogos": catalogos,
        "periodos": [{"anio": anio, "mes": mes} for anio, mes in periodos],
    })


def informe_exportaciones_rows(parametros):
    """(header, queryset, row function) for a stored report request; used by the Celery task."""
    columns = parametros["columnas"]
    desde, hasta = parse_periodo(parametros["periodo_desde"]), parse_periodo(parametros["periodo_hasta"])
    qs = filtered_exportaciones_informe(parametros.get("filtros", {}), desde=desde, hasta=hasta)
    catalogs = load_catalogs()
    bultos = _bultos_by_dus(desde, hasta, catalogs) if BULTO_COLUMNS.intersection(columns) else None
    docs = _docs_by_dus(desde, hasta) if DOC_COLUMNS.intersection(columns) else None
    return [EXPORT_COLUMN_MAP[key] for key in columns], qs, lambda row: [export_column_value(row, key, catalogs, bultos, docs) for key in columns]


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def exportar_informe_exportaciones(request):
    return solicitar_informe(request, "EXP", EXPORT_COLUMN_MAP, DEFAULT_EXPORT_COLUMNS, "informe_exportaciones")

"""Excel report builder for DUS exports (one row per DUS item)."""

import tempfile
from collections import defaultdict

import xlsxwriter
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from comercio.dus_txt import DUS_COLUMNS
from comercio.models import Exportacion, ExportacionBulto, ExportacionDocTransporte


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


def filtered_exportaciones_informe(filters, periodo_anio, periodo_mes):
    qs = Exportacion.objects.order_by("fecha_date", "numero_ident", "id")
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
    return qs


def _bultos_by_dus(periodo_anio, periodo_mes, catalogs):
    totals = defaultdict(lambda: [0, set()])
    rows = ExportacionBulto.objects.filter(periodo_anio=periodo_anio, periodo_mes=periodo_mes)
    for numero, cantidad, tipo in rows.values_list("numero_ident", "cantidad_bultos", "tipo_bulto_codigo").iterator(chunk_size=5000):
        try:
            totals[numero][0] += int(float(cantidad or 0))
        except ValueError:
            pass
        totals[numero][1].add(glosa(catalogs, "tipos_bulto", tipo) or tipo)
    return {numero: (total, ", ".join(sorted(tipos))) for numero, (total, tipos) in totals.items()}


def _docs_by_dus(periodo_anio, periodo_mes):
    docs = defaultdict(lambda: ([], [], []))
    rows = ExportacionDocTransporte.objects.filter(periodo_anio=periodo_anio, periodo_mes=periodo_mes).order_by("numero_ident", "secuencia")
    for numero, documento, nave, viaje in rows.values_list("numero_ident", "numero_documento", "nave", "numero_viaje").iterator(chunk_size=5000):
        for values, value in zip(docs[numero], (documento, nave, viaje)):
            if value and value not in values:
                values.append(value)
    return {numero: tuple(" | ".join(values) for values in lists) for numero, lists in docs.items()}


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
        total, tipos = (bultos or {}).get(row.numero_ident, ("", ""))
        return total if key == "total_bultos" else tipos
    if key in DOC_COLUMNS:
        values = (docs or {}).get(row.numero_ident, ("", "", ""))
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def exportar_informe_exportaciones(request):
    columns = [key for key in request.data.get("columnas", DEFAULT_EXPORT_COLUMNS) if key in EXPORT_COLUMN_MAP]
    if not columns:
        return Response({"detail": "Seleccione al menos una columna."}, status=status.HTTP_400_BAD_REQUEST)
    periodo_anio, periodo_mes = _int_or_none(request.data.get("periodo_anio")), _int_or_none(request.data.get("periodo_mes"))
    if not periodo_anio or not periodo_mes:
        return Response({"detail": "Indique mes y año del informe."}, status=status.HTTP_400_BAD_REQUEST)
    qs = filtered_exportaciones_informe(request.data.get("filtros", {}), periodo_anio, periodo_mes)
    catalogs = load_catalogs()
    bultos = _bultos_by_dus(periodo_anio, periodo_mes, catalogs) if BULTO_COLUMNS.intersection(columns) else None
    docs = _docs_by_dus(periodo_anio, periodo_mes) if DOC_COLUMNS.intersection(columns) else None
    return xlsx_response(
        f"informe_exportaciones_{periodo_anio}_{periodo_mes:02d}.xlsx", "Exportaciones",
        [EXPORT_COLUMN_MAP[key] for key in columns],
        ([export_column_value(row, key, catalogs, bultos, docs) for key in columns] for row in qs.iterator(chunk_size=2000)),
    )

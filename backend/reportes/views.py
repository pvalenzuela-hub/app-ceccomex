from django.http import HttpResponse
from django.db.models import Q
from openpyxl import Workbook
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from comercio.models import Importacion
from reportes.models import ImportadorProbable, ReporteSectorial, ReporteSectorialDetalle, RubroImportacion
from reportes.serializers import ImportadorProbableSerializer, ReporteSectorialDetalleSerializer, ReporteSectorialSerializer, RubroImportacionSerializer


# Indexed fields retain the official DIN position as stored in payload_json.raw_columns.
IMPORT_COLUMNS = [
    ("numero_ident", "Nº identificador"), ("item", "Ítem"), ("fecha_text", "Fecha"),
    ("aduana_codigo", "Código aduana"), ("comuna_importador_codigo", "Comuna importador"),
    ("pais_origen_codigo", "País de origen"), ("via_transporte_codigo", "Vía de transporte"),
    ("partida_arancelaria_codigo", "Arancel nacional"), ("glosa_mercancia", "Mercancía"),
    ("valor_fob", "Valor FOB"), ("valor_flete", "Valor flete"), ("valor_seguro", "Valor seguro"),
    ("valor_cif", "Valor CIF"), ("raw:28", "REG_IMP - Régimen de importación"),
    ("raw:61", "VALEXFAB - Valor Ex-Fábrica"), ("raw:63", "MONGASFOB - Gastos hasta FOB"),
    ("raw:73", "TOT_PESO - Total peso"), ("raw:146", "CANT_MERC - Cantidad de mercancías"),
    ("raw:148", "MEDIDA - Unidad de medida"), ("raw:149", "PRE_UNIT - Precio unitario FOB"),
    ("raw:162", "CIF_ITEM - Valor CIF del ítem"), ("raw:163", "ADVAL_ALA - Porcentaje advalorem"),
]
IMPORT_COLUMN_MAP = dict(IMPORT_COLUMNS)
DIN_LABELS = (
    "NUMENCRIPTADO", "TIPO_DOCTO", "ADU", "FORM", "FECVENCI", "CODCOMUN",
    "NUM_UNICO_IMPORTADOR", "CODPAISCON", "DESDIRALM", "CODCOMRS", "ADUCTROL", "NUMPLAZO",
    "INDPARCIAL", "NUMHOJINS", "TOTINSUM", "CODALMA", "NUM_RS", "FEC_RS", "ADUA_RS", "NUMHOJANE",
    "NUM_SEC", "PA_ORIG", "PA_ADQ", "VIA_TRAN", "TRANSB", "PTO_EMB", "PTO_DESEM", "TPO_CARGA",
    "ALMACEN", "FEC_ALMAC", "FECRETIRO", "NU_REGR", "ANO_REG", "CODVISBUEN", "NUMREGLA", "NUMANORES",
    "CODULTVB", "PAGO_GRAV", "FECTRA", "FECACEP", "GNOM_CIA_T", "CODPAISCIA", "NUMRUTCIA", "DIGVERCIA",
    "NUM_MANIF", "NUM_MANIF1", "NUM_MANIF2", "FEC_MANIF", "NUM_CONOC", "FEC_CONOC", "NOMEMISOR", "NUMRUTEMI",
    "DIGVEREMI", "GREG_IMP", "REG_IMP", "BCO_COM", "CODORDIV", "FORM_PAGO", "NUMDIAS", "VALEXFAB",
    "MONEDA", "MONGASFOB", "CL_COMPRA", "TOT_ITEMS", "FOB", "TOT_HOJAS", "COD_FLE", "FLETE",
    "TOT_BULTOS", "COD_SEG", "SEGURO", "TOT_PESO", "CIF", "NUM_AUT", "FEC_AUT", "GBCOCEN",
    "ID_BULTOS", "TPO_BUL1", "CANT_BUL1", "TPO_BUL2", "CANT_BUL2", "TPO_BUL3", "CANT_BUL3", "TPO_BUL4",
    "CANT_BUL4", "TPO_BUL5", "CANT_BUL5", "TPO_BUL6", "CANT_BUL6", "TPO_BUL7", "CANT_BUL7", "TPO_BUL8",
    "CANT_BUL8", "CTA_OTRO", "MON_OTRO", "CTA_OTR1", "MON_OTR1", "CTA_OTR2", "MON_OTR2", "CTA_OTR3",
    "MON_OTR3", "CTA_OTR4", "MON_OTR4", "CTA_OTR5", "MON_OTR5", "CTA_OTR6", "MON_OTR6", "CTA_OTR7",
    "MON_OTR7", "MON_178", "MON_191", "FEC_501", "VAL_601", "FEC_502", "VAL_602", "FEC_503",
    "VAL_603", "FEC_504", "VAL_604", "FEC_505", "VAL_605", "FEC_506", "VAL_606", "FEC_507",
    "VAL_607", "TASA", "NCUOTAS", "ADU_DI", "NUM_DI", "FEC_DI", "MON_699", "MON_199",
    "NUMITEM", "DNOMBRE", "DMARCA", "DVARIEDAD", "DOTRO1", "DOTRO2", "ATR-5", "ATR-6",
    "SAJU-ITEM", "AJU-ITEM", "CANT-MERC", "MERMAS", "MEDIDA", "PRE-UNIT", "ARANC-ALA", "NUMCOR",
    "NUMACU", "CODOBS1", "DESOBS1", "CODOBS2", "DESOBS2", "CODOBS3", "DESOBS3", "CODOBS4",
    "DESOBS4", "ARANC-NAC", "CIF-ITEM", "ADVAL-ALA", "ADVAL", "VALAD", "OTRO1", "CTA1",
    "SIGVAL1", "VAL1", "OTRO2", "CTA2", "SIGVAL2", "VAL2", "OTRO3", "CTA3",
    "SIGVAL3", "VAL3", "OTRO4", "CTA4", "SIGVAL4", "VAL4",
)
# Expose every official DIN position while preserving friendly materialized columns above.
IMPORT_COLUMNS.extend((f"raw:{index}", DIN_LABELS[index]) for index in range(178) if f"raw:{index}" not in IMPORT_COLUMN_MAP)
IMPORT_COLUMN_MAP = dict(IMPORT_COLUMNS)
DEFAULT_COLUMNS = ["numero_ident", "item", "fecha_text", "aduana_codigo", "pais_origen_codigo", "partida_arancelaria_codigo", "glosa_mercancia", "valor_fob", "valor_cif"]


def _selected_values(value):
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _filtered_importaciones(filters, periodo_anio, periodo_mes):
    qs = Importacion.objects.order_by("-creado")
    if periodo_anio:
        qs = qs.filter(periodo_anio=periodo_anio)
    if periodo_mes:
        qs = qs.filter(periodo_mes=periodo_mes)
    for field in ("aduana_codigo", "comuna_importador_codigo", "pais_origen_codigo", "via_transporte_codigo"):
        values = _selected_values(filters.get(field, []))
        if values:
            qs = qs.filter(**{f"{field}__in": values})
    tarifas = _selected_values(filters.get("partidas", []))
    if tarifas:
        qs = qs.filter(partida_arancelaria_codigo__in=tarifas)
    regimenes = _selected_values(filters.get("regimenes", []))
    if regimenes:
        qs = qs.filter(payload_json__raw_columns__28__in=regimenes)
    return qs


def _column_value(row, key):
    if key.startswith("raw:"):
        raw = row.payload_json.get("raw_columns", [])
        index = int(key.split(":", 1)[1])
        return raw[index] if index < len(raw) else ""
    return getattr(row, key, "")


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


@api_view(["GET"])
def importaciones_configuracion(request):
    grupos = {
        key: list(CatalogoCodigo.objects.filter(grupo=grupo).values("codigo", "glosa").order_by("codigo"))
        for key, grupo in {"ADUANAS": "aduanas", "COMUNAS": "comunas", "PAISES": "paises", "VIAS_TRANSPORTE": "via_transporte"}.items()
    }
    return Response({"columnas": [{"key": key, "label": label, "default": key in DEFAULT_COLUMNS} for key, label in IMPORT_COLUMNS], "catalogos": grupos})


@api_view(["GET", "POST"])
def rubros_importaciones(request):
    if request.method == "GET":
        return Response(RubroImportacionSerializer(RubroImportacion.objects.all(), many=True).data)
    serializer = RubroImportacionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(RubroImportacionSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
def rubro_importacion_detalle(request, rubro_id: int):
    rubro = RubroImportacion.objects.filter(id=rubro_id).first()
    if not rubro:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        rubro.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = RubroImportacionSerializer(rubro, data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(RubroImportacionSerializer(serializer.save()).data)


@api_view(["GET"])
def partidas_importacion(request):
    query = request.query_params.get("q", "").strip()
    rows = PartidaArancelaria.objects.all()
    if query:
        rows = rows.filter(Q(codigo__icontains=query) | Q(glosa__icontains=query))
    return Response(list(rows.order_by("codigo").values("codigo", "glosa")[:20]))


@api_view(["POST"])
def exportar_informe_importaciones(request):
    columns = [key for key in request.data.get("columnas", DEFAULT_COLUMNS) if key in IMPORT_COLUMN_MAP]
    if not columns:
        return Response({"detail": "Seleccione al menos una columna."}, status=status.HTTP_400_BAD_REQUEST)
    qs = _filtered_importaciones(request.data.get("filtros", {}), request.data.get("periodo_anio"), request.data.get("periodo_mes"))
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(title="Importaciones")
    sheet.append([IMPORT_COLUMN_MAP[key] for key in columns])
    for row in qs.iterator(chunk_size=1000):
        sheet.append([_column_value(row, key) for key in columns])
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="informe_importaciones.xlsx"'
    workbook.save(response)
    return response

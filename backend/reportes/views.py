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
    ("aduana_codigo", "Código aduana"), ("aduana_glosa", "Aduana - descripción"),
    ("comuna_importador_codigo", "Comuna importador"), ("comuna_importador_glosa", "Comuna importador - descripción"),
    ("pais_origen_codigo", "País de origen"), ("pais_origen_glosa", "País de origen - descripción"),
    ("via_transporte_codigo", "Vía de transporte"),
    ("pa_orig_glosa", "PA_ORIG - descripción"), ("pa_adq_glosa", "PA_ADQ - descripción"),
    ("via_transporte_glosa", "VIA_TRAN - descripción"), ("pto_emb_glosa", "PTO_EMB - descripción"),
    ("pto_desem_glosa", "PTO_DESEM - descripción"), ("reg_imp_glosa", "REG_IMP - descripción"),
    ("tipo_docto_glosa", "TIPO_DOCTO - descripción"), ("aductrol_glosa", "ADUCTROL - descripción"),
    ("adua_rs_glosa", "ADUA_RS - descripción"), ("codpaiscon_glosa", "CODPAISCON - descripción"),
    ("codcomrs_glosa", "CODCOMRS - descripción"), ("tpo_carga_glosa", "TPO_CARGA - descripción"),
    ("codvisbuen_glosa", "CODVISBUEN - descripción"), ("codultvb_glosa", "CODULTVB - descripción"),
    ("pago_grav_glosa", "PAGO_GRAV - descripción"), ("codpaiscia_glosa", "CODPAISCIA - descripción"),
    ("bco_com_glosa", "BCO_COM - descripción"), ("codordiv_glosa", "CODORDIV - descripción"),
    ("form_pago_glosa", "FORM_PAGO - descripción"), ("moneda_glosa", "MONEDA - descripción"),
    ("cl_compra_glosa", "CL_COMPRA - descripción"), ("medida_glosa", "MEDIDA - descripción"),
    ("tpo_bul1_glosa", "TPO_BUL1 - descripción"), ("tpo_bul2_glosa", "TPO_BUL2 - descripción"),
    ("tpo_bul3_glosa", "TPO_BUL3 - descripción"), ("tpo_bul4_glosa", "TPO_BUL4 - descripción"),
    ("tpo_bul5_glosa", "TPO_BUL5 - descripción"), ("tpo_bul6_glosa", "TPO_BUL6 - descripción"),
    ("tpo_bul7_glosa", "TPO_BUL7 - descripción"), ("tpo_bul8_glosa", "TPO_BUL8 - descripción"),
    ("partida_arancelaria_codigo", "Arancel nacional"), ("glosa_mercancia", "Mercancía"),
    ("valor_fob", "Valor FOB"), ("valor_flete", "Valor flete"), ("valor_seguro", "Valor seguro"),
    ("valor_cif", "Valor CIF"), ("raw:54", "REG_IMP - Régimen de importación"),
    ("raw:61", "VALEXFAB - Valor Ex-Fábrica"), ("raw:63", "MONGASFOB - Gastos hasta FOB"),
    ("raw:73", "TOT_PESO - Total peso"), ("raw:146", "CANT_MERC - Cantidad de mercancías"),
    ("raw:148", "MEDIDA - Unidad de medida"), ("raw:149", "PRE_UNIT - Precio unitario FOB"),
    ("raw:158", "CIF_ITEM - Valor CIF del ítem"), ("raw:160", "ADVAL - Porcentaje advalorem"),
    ("raw:162", "OTRO1"), ("raw:166", "OTRO2"), ("raw:170", "OTRO3"), ("raw:174", "OTRO4"),
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
DEFAULT_COLUMNS = ["numero_ident", "item", "fecha_text", "aduana_codigo", "aduana_glosa", "comuna_importador_codigo", "comuna_importador_glosa", "pais_origen_codigo", "pais_origen_glosa", "partida_arancelaria_codigo", "glosa_mercancia", "valor_fob", "valor_flete", "valor_seguro", "valor_cif", "raw:2", "raw:21", "pa_orig_glosa", "raw:22", "pa_adq_glosa", "raw:23", "via_transporte_glosa", "raw:25", "pto_emb_glosa", "raw:26", "pto_desem_glosa", "raw:54", "reg_imp_glosa", "raw:162", "raw:166", "raw:170", "raw:174"]


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
            qs = qs.filter(payload_json__raw_columns__54__in=regimenes)
    return qs


def _column_value(row, key, catalogos):
    raw = row.payload_json.get("raw_columns", [])
    raw_value = lambda index: raw[index] if index < len(raw) else ""
    glosa_fields = {
        "aduana_glosa": ("aduanas", row.aduana_codigo),
        "comuna_importador_glosa": ("comunas", row.comuna_importador_codigo),
        "pais_origen_glosa": ("paises", row.pais_origen_codigo),
        "pa_orig_glosa": ("paises", raw_value(21)),
        "pa_adq_glosa": ("paises", raw_value(22)),
        "via_transporte_glosa": ("via_transporte", raw_value(23)),
        "pto_emb_glosa": ("puertos", raw_value(25)),
        "pto_desem_glosa": ("puertos", raw_value(26)),
        "reg_imp_glosa": ("regimen_importacion", raw_value(54)),
        "tipo_docto_glosa": ("tipos_operacion_din", raw_value(1)),
        "aductrol_glosa": ("aduanas", raw_value(10)),
        "adua_rs_glosa": ("aduanas", raw_value(18)),
        "codpaiscon_glosa": ("paises", raw_value(7)),
        "codcomrs_glosa": ("comunas", raw_value(9)),
        "tpo_carga_glosa": ("tipos_carga", raw_value(27)),
        "codvisbuen_glosa": ("vistos_buenos", raw_value(33)),
        "codultvb_glosa": ("vistos_buenos", raw_value(36)),
        "pago_grav_glosa": ("formas_pago_gravamen", raw_value(37)),
        "codpaiscia_glosa": ("paises", raw_value(41)),
        "bco_com_glosa": ("bancos_comerciales", raw_value(55)),
        "codordiv_glosa": ("origen_divisas", raw_value(56)),
        "form_pago_glosa": ("formas_pago", raw_value(57)),
        "moneda_glosa": ("monedas", raw_value(60)),
        "cl_compra_glosa": ("clausulas_compra_venta", raw_value(62)),
        "medida_glosa": ("unidades_medida", raw_value(144)),
        **{f"tpo_bul{number}_glosa": ("tipos_bulto", raw_value(77 + (number - 1) * 2)) for number in range(1, 9)},
    }
    if key in glosa_fields:
        grupo, codigo = glosa_fields[key]
        return catalogos.get(grupo, {}).get(str(codigo), "")
    if key.startswith("raw:"):
        index = int(key.split(":", 1)[1])
        return raw_value(index)
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
        for key, grupo in {"ADUANAS": "aduanas", "COMUNAS": "comunas", "PAISES": "paises", "VIAS_TRANSPORTE": "via_transporte", "REGIMENES": "regimen_importacion"}.items()
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
    catalogos = {
        grupo: dict(CatalogoCodigo.objects.filter(grupo=grupo).values_list("codigo", "glosa"))
        for grupo in ("aduanas", "bancos_comerciales", "clausulas_compra_venta", "comunas", "formas_pago", "formas_pago_gravamen", "monedas", "origen_divisas", "paises", "puertos", "regimen_importacion", "tipos_bulto", "tipos_carga", "tipos_operacion_din", "unidades_medida", "via_transporte", "vistos_buenos")
    }
    for row in qs.iterator(chunk_size=1000):
        sheet.append([_column_value(row, key, catalogos) for key in columns])
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="informe_importaciones.xlsx"'
    workbook.save(response)
    return response

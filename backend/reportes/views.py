import unicodedata

from django.db.models import Func, Q, TextField
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.core.paginator import Paginator
from django.http import FileResponse
from kombu.exceptions import OperationalError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from comercio.legacy_mdb import LEGACY_COLUMNS
from comercio.models import Importacion
from reportes.models import ImportadorProbable, InformeExcel, PerfilImportador, ReporteSectorial, ReporteSectorialDetalle, RubroImportacion
from reportes.serializers import ImportadorProbableSerializer, ReporteSectorialDetalleSerializer, ReporteSectorialSerializer, RubroImportacionSerializer


# Indexed fields retain the official DIN position as stored in payload_json.raw_columns.
IMPORT_COLUMNS = [
    ("numero_ident", "Nº identificador"), ("importador_probable", "Importador probable sugerido"), ("item", "Ítem"), ("fecha_text", "Fecha"),
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
IMPORT_COLUMNS.extend((f"mdb:{name}", f"MDB 2015 - {name}") for name in LEGACY_COLUMNS)
IMPORT_COLUMN_MAP = dict(IMPORT_COLUMNS)
DEFAULT_COLUMNS = ["numero_ident", "importador_probable", "item", "fecha_text", "aduana_codigo", "aduana_glosa", "comuna_importador_codigo", "comuna_importador_glosa", "pais_origen_codigo", "pais_origen_glosa", "partida_arancelaria_codigo", "glosa_mercancia", "valor_fob", "valor_flete", "valor_seguro", "valor_cif", "raw:2", "raw:21", "pa_orig_glosa", "raw:22", "pa_adq_glosa", "raw:23", "via_transporte_glosa", "raw:25", "pto_emb_glosa", "raw:26", "pto_desem_glosa", "raw:54", "reg_imp_glosa", "raw:162", "raw:166", "raw:170", "raw:174"]

# Only map fields whose historical meaning matches the DIN TXT column.
LEGACY_DIN_NAMES = {
    "TIPO_DOCTO": "TIP_OPER", "ADU": "COD_ADU", "PA_ORIG": "PAI_ORI",
    "PA_ADQ": "PAI_ADQ", "VIA_TRAN": "VIA", "PTO_EMB": "PTO_EMB",
    "PTO_DESEM": "PTO_DES", "TPO_CARGA": "TIP_CAR", "REG_IMP": "REG_IMP",
    "MONEDA": "COD_MON", "CL_COMPRA": "COD_CLCOM", "FOB": "VAL_FOB",
    "COD_FLE": "COD_FLETE", "FLETE": "VAL_FLETE", "TOT_BULTOS": "TOT_BUL",
    "COD_SEG": "COD_SEG", "SEGURO": "MON_SEG", "TOT_PESO": "TOT_PESO",
    "CIF": "CIF_TOTAL", "NUMITEM": "NUM_ITEM", "DNOMBRE": "MERCADERIA",
    "CANT-MERC": "CANT_MERC", "MEDIDA": "COD_UMED", "PRE-UNIT": "PRE_UFOB",
    "ARANC-NAC": "COD_AAR", "CIF-ITEM": "CIF_ITEM",
}
LEGACY_DIN_NAMES.update({f"TPO_BUL{i}": f"TIP_BUL{i}" for i in range(1, 9)})
LEGACY_DIN_BY_INDEX = {
    index: LEGACY_DIN_NAMES[name] for index, name in enumerate(DIN_LABELS)
    if name in LEGACY_DIN_NAMES
}


def _selected_values(value):
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


# Product description fields: DIN TXT positions DNOMBRE..ATR-6 and their MDB 2015 equivalents.
PRODUCT_RAW_INDEXES = range(DIN_LABELS.index("DNOMBRE"), DIN_LABELS.index("ATR-6") + 1)
PRODUCT_LEGACY_FIELDS = ("MERCADERIA", "ATRI1", "ATRI2", "ATRI3", "ATRI4", "ATRI5", "ATRI6")


def _without_accents(text):
    return "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))


def _product_text():
    """Concatenate without separators: Aduana splits long descriptions mid-word across these fields."""
    raw = KeyTransform("raw_columns", "payload_json")
    legacy = KeyTransform("legacy_fields", "payload_json")
    parts = [KeyTextTransform(str(index), raw) for index in PRODUCT_RAW_INDEXES]
    parts += [KeyTextTransform(name, legacy) for name in PRODUCT_LEGACY_FIELDS]
    # A single flat CONCAT (NULL-skipping in PostgreSQL and SQLite 3.44+); Django's Concat nests one pair per field.
    return Func(*parts, function="CONCAT", output_field=TextField())


def parse_periodo(value):
    """{"anio": 2015, "mes": 1} -> (2015, 1), or None when absent or invalid."""
    try:
        anio, mes = int(value["anio"]), int(value["mes"])
    except (KeyError, TypeError, ValueError):
        return None
    return (anio, mes) if 1900 <= anio <= 2100 and 1 <= mes <= 12 else None


def _period_range_q(desde, hasta):
    return (
        (Q(periodo_anio__gt=desde[0]) | Q(periodo_anio=desde[0], periodo_mes__gte=desde[1]))
        & (Q(periodo_anio__lt=hasta[0]) | Q(periodo_anio=hasta[0], periodo_mes__lte=hasta[1]))
    )


def _filtered_importaciones(filters, periodo_anio=None, periodo_mes=None, desde=None, hasta=None):
    qs = Importacion.objects.select_related("importador_probable_sugerido").order_by("-creado")
    if desde and hasta:
        qs = qs.filter(_period_range_q(desde, hasta))
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
    paises_adquisicion = _selected_values(filters.get("pais_adquisicion_codigo", []))
    if paises_adquisicion:
        qs = qs.filter(
            Q(payload_json__raw_columns__22__in=paises_adquisicion)
            | Q(payload_json__legacy_fields__PAI_ADQ__in=paises_adquisicion)
        )
    importadores = [int(value) for value in _selected_values(filters.get("importadores", [])) if value.isdigit()]
    if importadores:
        qs = qs.filter(importador_probable_sugerido_id__in=importadores)
    productos = _selected_values(filters.get("productos", []))
    if productos:
        product_filter = Q()
        for term in productos:
            # Aduana descriptions are mostly unaccented ("NEUMATICOS"): also try the term without accents.
            for variant in {term, _without_accents(term)}:
                product_filter |= Q(texto_producto__icontains=variant)
        qs = qs.annotate(texto_producto=_product_text()).filter(product_filter)
    regimenes = _selected_values(filters.get("regimenes", []))
    if regimenes:
        qs = qs.filter(
            Q(payload_json__raw_columns__54__in=regimenes)
            | Q(payload_json__legacy_fields__REG_IMP__in=regimenes)
        )
    return qs


# Description columns: key -> (catalog group, model field name or DIN position).
GLOSA_COLUMNS = {
    "aduana_glosa": ("aduanas", "aduana_codigo"),
    "comuna_importador_glosa": ("comunas", "comuna_importador_codigo"),
    "pais_origen_glosa": ("paises", "pais_origen_codigo"),
    "pa_orig_glosa": ("paises", 21), "pa_adq_glosa": ("paises", 22),
    "via_transporte_glosa": ("via_transporte", 23), "pto_emb_glosa": ("puertos", 25),
    "pto_desem_glosa": ("puertos", 26), "reg_imp_glosa": ("regimen_importacion", 54),
    "tipo_docto_glosa": ("tipos_operacion_din", 1), "aductrol_glosa": ("aduanas", 10),
    "adua_rs_glosa": ("aduanas", 18), "codpaiscon_glosa": ("paises", 7),
    "codcomrs_glosa": ("comunas", 9), "tpo_carga_glosa": ("tipos_carga", 27),
    "codvisbuen_glosa": ("vistos_buenos", 33), "codultvb_glosa": ("vistos_buenos", 36),
    "pago_grav_glosa": ("formas_pago_gravamen", 37), "codpaiscia_glosa": ("paises", 41),
    "bco_com_glosa": ("bancos_comerciales", 55), "codordiv_glosa": ("origen_divisas", 56),
    "form_pago_glosa": ("formas_pago", 57), "moneda_glosa": ("monedas", 60),
    "cl_compra_glosa": ("clausulas_compra_venta", 62),
    "medida_glosa": ("unidades_medida", DIN_LABELS.index("MEDIDA")),
    **{f"tpo_bul{number}_glosa": ("tipos_bulto", 77 + (number - 1) * 2) for number in range(1, 9)},
}


def _column_value(row, key, catalogos):
    legacy = row.payload_json.get("legacy_fields", {})
    if key == "importador_probable":
        return row.importador_probable_sugerido.nombre if row.importador_probable_sugerido else legacy.get("IMPORT", "")
    if key.startswith("mdb:"):
        return legacy.get(key.split(":", 1)[1], "")
    raw = row.payload_json.get("raw_columns", [])
    def raw_value(index):
        if legacy:
            return legacy.get(LEGACY_DIN_BY_INDEX.get(index), "")
        return raw[index] if index < len(raw) else ""

    if key in GLOSA_COLUMNS:
        grupo, source = GLOSA_COLUMNS[key]
        codigo = raw_value(source) if isinstance(source, int) else getattr(row, source)
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
    query = request.query_params.get("q", "").strip()
    rows = ImportadorProbable.objects.all()
    ids = [int(value) for value in request.query_params.get("ids", "").split(",") if value.strip().isdigit()]
    if ids:
        # Lets saved report configurations show the names of their selected importers.
        return Response(ImportadorProbableSerializer(rows.filter(id__in=ids), many=True).data)
    if query:
        rut = query.replace(".", "").replace(" ", "").split("-")[0]
        rows = rows.filter(Q(rut__startswith=rut) if rut.isdigit() else Q(nombre__icontains=query))
    return Response(ImportadorProbableSerializer(rows[:50], many=True).data)


@api_view(["GET"])
def perfiles_importadores(request):
    if not request.user.is_authenticated:
        return Response({"detail": "Sesión no iniciada."}, status=status.HTTP_401_UNAUTHORIZED)
    search = request.query_params.get("search", "").strip()
    rows = PerfilImportador.objects.all()
    if search:
        rows = rows.filter(Q(rut__icontains=search) | Q(dv__icontains=search) | Q(nombre__icontains=search))
    page = Paginator(rows.order_by("nombre"), 25).get_page(request.query_params.get("page", 1))
    return Response({"count": page.paginator.count, "results": list(page.object_list.values("id", "rut", "dv", "nombre", "total_evidencias", "primer_periodo_anio", "primer_periodo_mes", "ultimo_periodo_anio", "ultimo_periodo_mes", "aranceles_json", "rubros_json"))})


@api_view(["GET"])
def importaciones_configuracion(request):
    grupos = {
        key: list(CatalogoCodigo.objects.filter(grupo=grupo).values("codigo", "glosa").order_by("codigo"))
        for key, grupo in {"ADUANAS": "aduanas", "COMUNAS": "comunas", "PAISES": "paises", "VIAS_TRANSPORTE": "via_transporte", "REGIMENES": "regimen_importacion"}.items()
    }
    periodos = Importacion.objects.values_list("periodo_anio", "periodo_mes").distinct().order_by("-periodo_anio", "-periodo_mes")
    return Response({
        "columnas": [{"key": key, "label": label, "default": key in DEFAULT_COLUMNS} for key, label in IMPORT_COLUMNS],
        "catalogos": grupos,
        "periodos": [{"anio": anio, "mes": mes} for anio, mes in periodos if anio and mes],
    })


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


IMPORT_CATALOG_GROUPS = (
    "aduanas", "bancos_comerciales", "clausulas_compra_venta", "comunas", "formas_pago", "formas_pago_gravamen",
    "monedas", "origen_divisas", "paises", "puertos", "regimen_importacion", "tipos_bulto", "tipos_carga",
    "tipos_operacion_din", "unidades_medida", "via_transporte", "vistos_buenos",
)


def informe_importaciones_rows(parametros):
    """(header, queryset, row function) for a stored report request; shared by the Celery task."""
    columns = parametros["columnas"]
    desde, hasta = parse_periodo(parametros["periodo_desde"]), parse_periodo(parametros["periodo_hasta"])
    qs = _filtered_importaciones(parametros.get("filtros", {}), desde=desde, hasta=hasta)
    catalogos = {grupo: dict(CatalogoCodigo.objects.filter(grupo=grupo).values_list("codigo", "glosa")) for grupo in IMPORT_CATALOG_GROUPS}
    return [IMPORT_COLUMN_MAP[key] for key in columns], qs, lambda row: [_column_value(row, key, catalogos) for key in columns]


def _informe_json(informe):
    return {
        "id": informe.id, "estado": informe.estado, "filas_total": informe.filas_total,
        "filas_procesadas": informe.filas_procesadas, "error": informe.error, "nombre_descarga": informe.nombre_descarga,
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def exportar_informe_importaciones(request):
    columns = [key for key in request.data.get("columnas", DEFAULT_COLUMNS) if key in IMPORT_COLUMN_MAP]
    if not columns:
        return Response({"detail": "Seleccione al menos una columna."}, status=status.HTTP_400_BAD_REQUEST)
    # A single month (periodo_anio/periodo_mes) is still accepted as a one-month range.
    single = {"anio": request.data.get("periodo_anio"), "mes": request.data.get("periodo_mes")}
    desde = parse_periodo(request.data.get("periodo_desde") or single)
    hasta = parse_periodo(request.data.get("periodo_hasta") or single)
    if not desde or not hasta:
        return Response({"detail": "Indique mes y año desde y hasta."}, status=status.HTTP_400_BAD_REQUEST)
    if desde > hasta:
        return Response({"detail": "El período desde no puede ser posterior al período hasta."}, status=status.HTTP_400_BAD_REQUEST)
    informe = InformeExcel.objects.create(
        tipo="IMP", usuario=request.user,
        parametros_json={
            "columnas": columns, "filtros": request.data.get("filtros", {}),
            "periodo_desde": {"anio": desde[0], "mes": desde[1]}, "periodo_hasta": {"anio": hasta[0], "mes": hasta[1]},
        },
        nombre_descarga=f"informe_importaciones_{desde[0]}-{desde[1]:02d}_a_{hasta[0]}-{hasta[1]:02d}.xlsx",
    )
    from reportes.tasks import generar_informe_importaciones

    try:
        generar_informe_importaciones.delay(informe.id)
    except OperationalError:
        generar_informe_importaciones(informe.id)
    informe.refresh_from_db()
    return Response(_informe_json(informe), status=status.HTTP_202_ACCEPTED)


def _own_informe(request, informe_id):
    informe = InformeExcel.objects.filter(id=informe_id).first()
    if informe and (informe.usuario_id == request.user.id or request.user.is_superuser):
        return informe
    return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def informe_estado(request, informe_id: int):
    informe = _own_informe(request, informe_id)
    if not informe:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(_informe_json(informe))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def informe_descargar(request, informe_id: int):
    from reportes.tasks import informe_path

    informe = _own_informe(request, informe_id)
    if not informe or informe.estado != "LISTO" or not informe_path(informe).is_file():
        return Response({"detail": "Informe no disponible."}, status=status.HTTP_404_NOT_FOUND)
    return FileResponse(
        informe_path(informe).open("rb"), as_attachment=True, filename=informe.nombre_descarga,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

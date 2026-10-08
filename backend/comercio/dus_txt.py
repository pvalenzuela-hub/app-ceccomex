"""Streaming parser for the monthly DUS export TXT files (base, bultos and documentos de transporte)."""

import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation


# Column order from doc-req/export/descripcion-y-estructura-de-datos- dus.xlsx (hoja "titulos").
DUS_COLUMNS = tuple("""
    FECHAACEPT NUMEROIDENT ADUANA TIPOOPERACION CODIGORUTEXPORTADORPPAL NRO_EXPORTADOR
    PORCENTAJEEXPPPAL COMUNAEXPORTADORPPAL CODIGORUTEXPSEC NRO_EXPORTADOR_SEC
    PORCENTAJEEXPSECUNDARIO COMUNAEXPSECUNDARIO PUERTOEMB GLOSAPUERTOEMB REGIONORIGEN
    TIPOCARGA VIATRANSPORTE PUERTODESEMB GLOSAPUERTODESEMB PAISDESTINO GLOSAPAISDESTINO
    NOMBRECIATRANSP PAISCIATRANSP RUTCIATRANSP DVRUTCIATRANSP NOMBREEMISORDOCTRANSP
    RUTEMISOR DVRUTEMISOR CODIGOTIPOAUTORIZA NUMEROINFORMEEXPO DVNUMEROINFORMEEXP
    FECHAINFORMEEXP MONEDA MODALIDADVENTA CLAUSULAVENTA FORMAPAGO VALORCLAUSULAVENTA
    COMISIONESEXTERIOR OTROSGASTOS VALORLIQUIDORETORNO NUMEROREGSUSP ADUANAREGSUSP
    PLAZOVIGENCIAREGSUSP TOTALITEM TOTALBULTOS PESOBRUTOTOTAL TOTALVALORFOB VALORFLETE
    CODIGOFLETE VALORSEGURO CODIGOSEG VALORCIF NUMEROPARCIALIDAD TOTALPARCIALES PARCIAL
    OBSERVACION NUMERODOCTOCANCELA FECHADOCTOCANCELA TIPODOCTOCANCELA PESOBRUTOCANCELA
    TOTALBULTOSCANCELA NUMEROITEM NOMBRE ATRIBUTO1 ATRIBUTO2 ATRIBUTO3 ATRIBUTO4 ATRIBUTO5
    ATRIBUTO6 CODIGOARANCEL UNIDADMEDIDA CANTIDADMERCANCIA FOBUNITARIO FOBUS
    CODIGOOBSERVACION1 VALOROBSERVACION1 GLOSAOBSERVACION1 CODIGOOBSERVACION2
    VALOROBSERVACION2 GLOSAOBSERVACION2 CODIGOOBSERVACION3 VALOROBSERVACION3
    GLOSAOBSERVACION3 PESOBRUTOITEM
""".split())
BULTO_COLUMNS = ("NUMEROIDENT", "FECHAACEPT", "NUMEROBULTO", "TIPOBULTO", "CANTIDADBULTO", "IDENTIFICACIONBULTO")
DOC_COLUMNS = ("NUMEROIDENT", "FECHAACEPT", "NSECDOCTRANSP", "NUMERODOCTRANSP", "FECHADOCTRANSP", "NOMBRENAVE", "NUMEROVIAJE")

SOURCE_FORMAT = "DUS_TXT"
# Aduana publishes fixed-width lines; a few base rows are cut at 722 bytes after NOMBRE
# and a few document rows lose NUMEROVIAJE. Those rows are kept and flagged.
MIN_DUS_COLUMNS = DUS_COLUMNS.index("NOMBRE") + 1
MIN_DOC_COLUMNS = len(DOC_COLUMNS) - 1
DUS_AMOUNT_COLUMNS = (
    "CANTIDADMERCANCIA", "FOBUNITARIO", "FOBUS", "PESOBRUTOITEM", "TOTALVALORFOB",
    "VALORFLETE", "VALORSEGURO", "VALORCIF", "VALORLIQUIDORETORNO",
)
TIPOS = ("EXP_BASE", "EXP_BULTO", "EXP_DOC")


def member_tipo(name):
    """Classify a ZIP member by its Aduana file name ("... – Bultos.txt", "... – Documentos de Transporte.txt")."""
    base = unicodedata.normalize("NFKD", name.rsplit("/", 1)[-1]).encode("ascii", "ignore").decode().lower()
    if not base.endswith(".txt"):
        return None
    if "bulto" in base:
        return "EXP_BULTO"
    if "documento" in base and "transporte" in base:
        return "EXP_DOC"
    if "exportacion" in base:
        return "EXP_BASE"
    return None


def iter_fields(binary_stream):
    """Yield (line_number, fields) splitting on LF only; Aduana fields may contain stray CR or TAB."""
    for number, raw in enumerate(binary_stream, start=1):
        line = raw.rstrip(b"\r\n").decode("latin-1").replace("\r", " ").replace("\t", " ").rstrip()
        if line:
            yield number, line.split(";")


def _date(value, name, *, required):
    value = value.strip()
    if not value or set(value) == {"0"}:
        if required:
            raise ValueError(f"{name} ausente")
        return None
    try:
        return datetime.strptime(value.zfill(8), "%d%m%Y").date()
    except ValueError as exc:
        raise ValueError(f"{name} inválida: {value!r}") from exc


def _amount(value, name):
    """Normalize Aduana decimal commas to a plain dotted string; blank stays blank."""
    value = value.strip()
    if not value:
        return ""
    try:
        amount = Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"{name} no numérico: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"{name} no finito: {value!r}")
    result = format(amount, "f")
    if len(result) > 32:
        raise ValueError(f"{name} demasiado largo: {value!r}")
    return result


def _named(columns, fields):
    return {name: value.strip() for name, value in zip(columns, fields) if value.strip()}


def _check_period(fecha, periodo):
    if (fecha.year, fecha.month) != periodo:
        raise ValueError(f"FECHAACEPT {fecha:%d-%m-%Y} fuera del período {periodo[1]:02d}/{periodo[0]}")


def map_exportacion(fields, periodo):
    if len(fields) > len(DUS_COLUMNS) or len(fields) < MIN_DUS_COLUMNS:
        raise ValueError(f"{len(fields)} columnas, se esperaban {len(DUS_COLUMNS)}")
    incompleto = len(fields) < len(DUS_COLUMNS)
    row = dict(zip(DUS_COLUMNS, (value.strip() for value in fields)))
    row.update({name: "" for name in DUS_COLUMNS[len(fields):]})
    numero, item = row["NUMEROIDENT"], row["NUMEROITEM"]
    if not numero or not item:
        raise ValueError("Falta NUMEROIDENT o NUMEROITEM")
    if not incompleto and not row["CODIGOARANCEL"]:
        raise ValueError("Falta CODIGOARANCEL")
    fecha = _date(row["FECHAACEPT"], "FECHAACEPT", required=True)
    _check_period(fecha, periodo)
    amounts = {name: _amount(row[name], name) for name in DUS_AMOUNT_COLUMNS}
    payload = {"source_format": SOURCE_FORMAT, "dus_fields": _named(DUS_COLUMNS, fields)}
    if incompleto:
        payload["columnas_recibidas"] = len(fields)
    return {
        "periodo_anio": periodo[0],
        "periodo_mes": periodo[1],
        "numero_ident": numero,
        "item": item,
        "fecha_text": fecha.isoformat(),
        "fecha_date": fecha,
        "aduana_codigo": row["ADUANA"],
        "tipo_operacion_codigo": row["TIPOOPERACION"],
        "exportador_codigo": row["NRO_EXPORTADOR"],
        "comuna_exportador_codigo": row["COMUNAEXPORTADORPPAL"],
        "region_origen_codigo": row["REGIONORIGEN"],
        "puerto_embarque_codigo": row["PUERTOEMB"],
        "puerto_desembarque_codigo": row["PUERTODESEMB"],
        "pais_destino_codigo": row["PAISDESTINO"],
        "via_transporte_codigo": row["VIATRANSPORTE"],
        "partida_arancelaria_codigo": row["CODIGOARANCEL"],
        "glosa_mercancia": row["NOMBRE"],
        "unidad_medida_codigo": row["UNIDADMEDIDA"],
        "cantidad_mercancia": amounts["CANTIDADMERCANCIA"],
        "valor_fob_unitario": amounts["FOBUNITARIO"],
        "valor_fob": amounts["FOBUS"],
        "peso_bruto_item": amounts["PESOBRUTOITEM"],
        "valor_fob_dus": amounts["TOTALVALORFOB"],
        "valor_flete_dus": amounts["VALORFLETE"],
        "valor_seguro_dus": amounts["VALORSEGURO"],
        "valor_cif_dus": amounts["VALORCIF"],
        "valor_liquido_retorno_dus": amounts["VALORLIQUIDORETORNO"],
        "registro_incompleto": incompleto,
        "payload_json": payload,
    }


def map_bulto(fields, periodo):
    if len(fields) != len(BULTO_COLUMNS):
        raise ValueError(f"{len(fields)} columnas, se esperaban {len(BULTO_COLUMNS)}")
    row = dict(zip(BULTO_COLUMNS, (value.strip() for value in fields)))
    if not row["NUMEROIDENT"] or not row["NUMEROBULTO"]:
        raise ValueError("Falta NUMEROIDENT o NUMEROBULTO")
    fecha = _date(row["FECHAACEPT"], "FECHAACEPT", required=True)
    _check_period(fecha, periodo)
    return {
        "periodo_anio": periodo[0],
        "periodo_mes": periodo[1],
        "numero_ident": row["NUMEROIDENT"],
        "fecha_text": fecha.isoformat(),
        "fecha_date": fecha,
        "secuencia": row["NUMEROBULTO"],
        "tipo_bulto_codigo": row["TIPOBULTO"],
        "cantidad_bultos": _amount(row["CANTIDADBULTO"], "CANTIDADBULTO"),
        "marcas": row["IDENTIFICACIONBULTO"][:255],
        "payload_json": {"source_format": SOURCE_FORMAT, "dus_fields": _named(BULTO_COLUMNS, fields)},
    }


def map_doc_transporte(fields, periodo):
    if len(fields) > len(DOC_COLUMNS) or len(fields) < MIN_DOC_COLUMNS:
        raise ValueError(f"{len(fields)} columnas, se esperaban {len(DOC_COLUMNS)}")
    incompleto = len(fields) < len(DOC_COLUMNS)
    row = dict(zip(DOC_COLUMNS, (value.strip() for value in fields)))
    row.setdefault("NUMEROVIAJE", "")
    if not row["NUMEROIDENT"] or not row["NSECDOCTRANSP"]:
        raise ValueError("Falta NUMEROIDENT o NSECDOCTRANSP")
    fecha = _date(row["FECHAACEPT"], "FECHAACEPT", required=True)
    _check_period(fecha, periodo)
    fecha_documento = _date(row["FECHADOCTRANSP"], "FECHADOCTRANSP", required=False)
    payload = {"source_format": SOURCE_FORMAT, "dus_fields": _named(DOC_COLUMNS, fields)}
    if incompleto:
        payload["columnas_recibidas"] = len(fields)
    return {
        "periodo_anio": periodo[0],
        "periodo_mes": periodo[1],
        "numero_ident": row["NUMEROIDENT"],
        "fecha_text": fecha.isoformat(),
        "fecha_date": fecha,
        "secuencia": row["NSECDOCTRANSP"],
        "numero_documento": row["NUMERODOCTRANSP"],
        "fecha_documento_text": fecha_documento.isoformat() if fecha_documento else "",
        "nave": row["NOMBRENAVE"],
        "numero_viaje": row["NUMEROVIAJE"],
        "registro_incompleto": incompleto,
        "payload_json": payload,
    }


MAPPERS = {"EXP_BASE": map_exportacion, "EXP_BULTO": map_bulto, "EXP_DOC": map_doc_transporte}
# Unique key inside one monthly file.
KEY_FIELDS = {"EXP_BASE": ("numero_ident", "item"), "EXP_BULTO": ("numero_ident", "secuencia"), "EXP_DOC": ("numero_ident", "secuencia")}
FECHA_INDEX = {"EXP_BASE": DUS_COLUMNS.index("FECHAACEPT"), "EXP_BULTO": 1, "EXP_DOC": 1}
_PERIOD_RE = re.compile(r"\d{7,8}")


def detect_period(binary_stream, tipo):
    """Period (year, month) from the first data line's FECHAACEPT."""
    for _, fields in iter_fields(binary_stream):
        value = fields[FECHA_INDEX[tipo]].strip() if len(fields) > FECHA_INDEX[tipo] else ""
        if not _PERIOD_RE.fullmatch(value):
            raise ValueError(f"FECHAACEPT inválida en la primera línea: {value!r}")
        fecha = _date(value, "FECHAACEPT", required=True)
        return fecha.year, fecha.month
    raise ValueError("Archivo vacío")

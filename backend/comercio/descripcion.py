"""Split the DIN item description into product code, name, brand and attributes, and read the observed quantity.

Importers declare "CODE~NAME~BRAND-F~ATTR~ATTR..." and Aduana cuts that text into DNOMBRE (50 chars) and
DMARCA, DVARIEDAD, DOTRO1, DOTRO2, ATR-5, ATR-6 (30 chars each), often mid-word, so the attribute fields are
read as one line. Most declarations fill the fields one by one instead ("CODE~NAME" in DNOMBRE, "BRAND-F" in
DMARCA, one attribute per field); then the field boundaries are kept. The brand ends with "-F", which the
30-char cut may split between DMARCA and DVARIEDAD. The text before the first "~" (product code, often
"SIN-CODIGO") is appended to the last filled of DOTRO1, DOTRO2, ATR-5, ATR-6. MDB 2015 rows have the same
fields without the code.
"""

import re

# DNOMBRE, DMARCA, DVARIEDAD, DOTRO1, DOTRO2, ATR-5, ATR-6 (doc-req/import/descripcion-y-estructura-de-datos-din.xlsx)
DESCRIPCION_POSITIONS = range(133, 140)
DESCRIPCION_MDB_FIELDS = ("MERCADERIA", "ATRI1", "ATRI2", "ATRI3", "ATRI4", "ATRI5", "ATRI6")
DESOBS_POSITIONS = (150, 152, 154, 156)
DESOBS_MDB_FIELDS = ("DES_OB1", "DES_OB2", "DES_OB3", "DES_OB4")
# Brand terminator: "-F" closing the text, a field, or followed by a separator ("SEYTEX-F~", "WELLA-F ").
BRAND_END = re.compile(r"-F(?=$|[\s~.,;:/])")
# "00000081.000000 T.M", "00053773.000000 KILOS"; short codes such as "001 CANCELA" are not quantities.
CANTIDAD_UNIDAD = re.compile(r"^\s*(\d+\.\d+|\d{6,})\s+([^\d\s].*?)\s*$")


def _clean(text):
    return " ".join(text.replace("~", " ").split())


def _brand_end(line, starts):
    """(start, end) of the "-F" ending the brand, also when the 30-char cut leaves "-" and "F" in different fields."""
    for match in re.finditer("-F", line):
        start, end = match.span()
        if BRAND_END.match(line, start) or end in starts or start + 1 in starts:
            return start, end
    return None


def _ancho(value, width):
    """A field one character short of its width lost a trailing space when Aduana trimmed it."""
    return value + " " if len(value) == width - 1 else value


def separar_descripcion(dnombre, atributos):
    """[DNOMBRE, DMARCA, DVARIEDAD, DOTRO1, DOTRO2, ATR-5, ATR-6] as name, brand and attributes."""
    atributos = [_ancho(value, 30) for value in ([value or "" for value in atributos] + [""] * 6)[:6]]
    codigo, tilde, nombre = _ancho(dnombre or "", 50).partition("~")
    if not tilde:
        codigo, nombre = "", codigo
    nombre = nombre.lstrip("~ ")  # "10KG~~ EXTINTOR"
    line = "".join(atributos)
    if "~" in nombre:
        # Whole description as one "~" line: NAME~BRAND-F~ATTR~...
        nombre, _, resto = (nombre + line).partition("~")
        span = _brand_end(resto, ())
        corte = resto.find("~")
        if span and (corte < 0 or span[0] < corte):
            marca, resto = resto[:span[0]], resto[span[1]:]
        else:
            marca, resto = (resto[:corte], resto[corte:]) if corte >= 0 else (resto, "")
        otros = [_clean(part) for part in resto.split("~")]
        otros = [value for value in otros if value]
    else:
        starts, position = set(), 0
        for value in atributos:
            position += len(value)
            starts.add(position)
        span = _brand_end(line, starts)
        # The brand may run into DVARIEDAD only when DMARCA was cut at its 30 characters.
        limite = len(atributos[0]) + (len(atributos[1]) if len(atributos[0]) >= 29 else 0)
        if not span or span[0] >= limite:
            span = (len(atributos[0]), len(atributos[0]))
        marca, fin = line[:span[0]], span[1]
        if "~" in line[fin:]:
            otros = [value for value in (_clean(part) for part in line[fin:].split("~")) if value]
        else:
            otros, position = [], 0
            for value in atributos:
                otros.append(_clean(value[max(fin - position, 0):]) if position + len(value) > fin else "")
                position += len(value)
            otros = otros[1:]
    otros = (otros + [""] * 5)[:4] + [" ".join(value for value in otros[4:] if value)]
    codigo = codigo.strip()
    if codigo:
        destino = max((index for index in range(1, 5) if otros[index]), default=1)
        otros[destino] = f"{otros[destino]} {codigo}".strip()
    return [_clean(nombre), _clean(marca), *otros]


def cantidad_observada(descripciones):
    """(quantity, unit) from the first DESOBS1..DESOBS4 holding "00000081.000000 T.M"; ("", "") when none does."""
    for value in descripciones:
        match = CANTIDAD_UNIDAD.match(value or "")
        if match:
            return float(match.group(1)), match.group(2)
    return "", ""


def campos_descripcion(payload):
    """Derived item fields of an Importacion payload (DIN TXT raw_columns or MDB 2015 legacy_fields)."""
    legacy = payload.get("legacy_fields")
    if legacy:
        valores = [legacy.get(name, "") for name in DESCRIPCION_MDB_FIELDS]
        observaciones = [legacy.get(name, "") for name in DESOBS_MDB_FIELDS]
    else:
        raw = payload.get("raw_columns", [])
        valores = [raw[index] if index < len(raw) else "" for index in DESCRIPCION_POSITIONS]
        observaciones = [raw[index] if index < len(raw) else "" for index in DESOBS_POSITIONS]
    cantidad, unidad = cantidad_observada(observaciones)
    return {"descripcion": separar_descripcion(valores[0], valores[1:]), "cantidad_observada": cantidad, "unidad_observada": unidad}

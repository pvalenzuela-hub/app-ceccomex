"""Searchable product text, stored per row in `texto_producto` and indexed with pg_trgm.

Customs split long descriptions across several fields, often mid-word, so the fields are joined
without separators. Text is uppercased and stripped of accents so "neumáticos" finds "NEUMATICOS".
"""

import unicodedata


# DIN TXT positions DNOMBRE..ATR-6 (doc-req/import/descripcion-y-estructura-de-datos-din.xlsx).
DIN_PRODUCT_POSITIONS = range(133, 140)
MDB_PRODUCT_FIELDS = ("MERCADERIA", "ATRI1", "ATRI2", "ATRI3", "ATRI4", "ATRI5", "ATRI6")
DUS_PRODUCT_FIELDS = ("NOMBRE", "ATRIBUTO1", "ATRIBUTO2", "ATRIBUTO3", "ATRIBUTO4", "ATRIBUTO5", "ATRIBUTO6")


def normalizar(text):
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(char for char in decomposed if not unicodedata.combining(char)).upper()


def texto_producto_importacion(payload):
    legacy = payload.get("legacy_fields")
    if legacy:
        parts = [legacy.get(name, "") for name in MDB_PRODUCT_FIELDS]
    else:
        raw = payload.get("raw_columns", [])
        parts = [raw[index] if index < len(raw) else "" for index in DIN_PRODUCT_POSITIONS]
    return normalizar("".join(part or "" for part in parts))


def texto_producto_exportacion(payload):
    fields = payload.get("dus_fields", {})
    return normalizar("".join(fields.get(name, "") for name in DUS_PRODUCT_FIELDS))

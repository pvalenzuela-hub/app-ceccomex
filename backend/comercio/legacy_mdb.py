"""Streaming conversion of the monthly Jet 3 import files (IM201501-IM201506)."""

import csv
import io
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from comercio.busqueda import texto_producto_importacion


EXPECTED_ROWS = {
    1: 274536,
    2: 262511,
    3: 306900,
    4: 280979,
    5: 264342,
    6: 319103,
}
SOURCE_FORMAT = "MDB_JET3_2015"
MEMBER_PATTERN = re.compile(r"IM20150([1-6])\.mdb", re.IGNORECASE)
LEGACY_COLUMNS = tuple("""
    NUM_IDEN TIP_OPER COD_ADU IMPORT RUT DV NUM_REGS FEC_REGS ADU_REGS
    PAI_ORI PAI_ADQ ZON_ECO VIA PTO_EMB PTO_DES TIP_CAR COD_ALM FEC_ALM
    FEC_RM NUM_REGI ANO_REGI REG_VB FPA_GRA FEC_ACE ART_DEN NOM_CIA
    COD_PCIA RUT_CIA DV_CIA NUM_MA NUM_MA1 NUM_MA2 FEC_MAN NUM_DOCT
    FEC_DOCT REG_IMP BCO_COM FPA_COB COD_MON COD_CLCOM NUM_ITEMT
    VAL_FOB COD_FLETE VAL_FLETE TOT_BUL COD_SEG MON_SEG TOT_PESO
    CIF_TOTAL NUM_IIMP FEC_IIMP IDE_BULTOS IDE_BULTO2 TIP_BUL1 CAN_BUL1
    TIP_BUL2 CAN_BUL2 TIP_BUL3 CAN_BUL3 TIP_BUL4 CAN_BUL4 TIP_BUL5
    CAN_BUL5 TIP_BUL6 CAN_BUL6 TIP_BUL7 CAN_BUL7 TIP_BUL8 CAN_BUL8
    COD_CADV MON_CADV COD_CO1 MON_CO1 COD_CO2 MON_CO2 COD_CO3 MON_CO3
    COD_CO4 MON_CO4 COD_CO5 MON_CO5 COD_CO6 MON_CO6 COD_CO7 MON_CO7
    MON_CIVA MON_GIRO MON_DIFE MON_CCON NUM_ITEM MERCADERIA ATRI1
    ATRI2 ATRI3 ATRI4 ATRI5 ATRI6 CLA_ECO SIG_AJU MON_AJU CANT_MERC
    MERMAS COD_UMED PRE_UFOB COD_ARAT NUM_CARA NUM_ACOM COD_OB1
    DES_OB1 COD_OB2 DES_OB2 COD_OB3 DES_OB3 COD_OB4 DES_OB4 COD_AAR
    CIF_ITEM POR_ADV COD_CADVI MON_CADVI POR_CO1 COD_COT1 SIG_CO1
    MON_COT1 POR_CO2 COD_COT2 SIG_CO2 MON_COT2 POR_CO3 COD_COT3
    SIG_CO3 MON_COT3 POR_CO4 COD_COT4 SIG_CO4 MON_COT4 FOB_ITEM
    FLE_ITEM SEG_ITEM PRE_UCIF PERIODO
""".split())
def member_month(name):
    match = MEMBER_PATTERN.fullmatch(name)
    if not match:
        raise ValueError(f"Archivo MDB inesperado: {name}")
    return int(match.group(1))


def _money(value, name):
    if value is None or not str(value).strip():
        raise ValueError(f"Valor monetario ausente: {name}")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"Valor monetario inválido: {name}") from exc
    if not amount.is_finite():
        raise ValueError(f"Valor monetario no finito: {name}")
    result = format(amount, "f")
    if len(result) > 32:
        raise ValueError(f"Valor monetario demasiado largo: {name}")
    return result


def map_importacion(row, month):
    """Keep the original named columns; never interpret them as 178-position DIN TXT."""
    period = f"2015{month:02d}"
    if row["PERIODO"].strip() != period:
        raise ValueError(f"PERIODO distinto de {period}: {row['PERIODO']!r}")
    numero = row["NUM_IDEN"].strip()
    item = row["NUM_ITEM"].strip()
    partida = row["COD_AAR"].strip()
    if not numero or not item or not partida:
        raise ValueError("Falta NUM_IDEN, NUM_ITEM o COD_AAR")
    fecha_original = row["FEC_ACE"].strip()
    try:
        fecha = datetime.strptime(fecha_original.zfill(8), "%d%m%Y").date()
    except ValueError as exc:
        raise ValueError(f"FEC_ACE inválida: {fecha_original!r}") from exc
    if fecha.year != 2015 or fecha.month != month:
        raise ValueError(f"FEC_ACE fuera del período {period}: {fecha_original!r}")

    legacy = {key: value.strip() if value is not None else "" for key, value in row.items()}
    payload = {"source_format": SOURCE_FORMAT, "legacy_fields": legacy}
    return {
        "periodo_anio": 2015,
        "periodo_mes": month,
        "numero_ident": numero,
        "item": item,
        "fecha_text": fecha.isoformat(),
        "fecha_date": fecha,
        "aduana_codigo": row["COD_ADU"].strip(),
        "comuna_importador_codigo": "",  # Not present in the historic MDB.
        "pais_origen_codigo": row["PAI_ORI"].strip(),
        "via_transporte_codigo": row["VIA"].strip(),
        "partida_arancelaria_codigo": partida,
        "glosa_mercancia": row["MERCADERIA"].strip(),
        "valor_fob": _money(row["FOB_ITEM"], "FOB_ITEM"),
        "valor_flete": _money(row["FLE_ITEM"], "FLE_ITEM"),
        "valor_seguro": _money(row["SEG_ITEM"], "SEG_ITEM"),
        "valor_cif": _money(row["CIF_ITEM"], "CIF_ITEM"),
        "texto_producto": texto_producto_importacion(payload),
        "payload_json": payload,
    }


@contextmanager
def export_rows(archive, member, *, temp_dir=None):
    """Extract one MDB at a time; stream mdb-export stdout without a CSV copy."""
    with tempfile.TemporaryDirectory(prefix="legacy-mdb-", dir=temp_dir) as directory:
        mdb_path = Path(directory) / member
        with archive.open(member) as source, mdb_path.open("wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)

        with (Path(directory) / "mdb-export.stderr").open("w+") as errors:
            process = subprocess.Popen(
                ["mdb-export", str(mdb_path), Path(member).stem],
                stdout=subprocess.PIPE,
                stderr=errors,
                env={**os.environ, "LC_ALL": "C.UTF-8"},
            )
            try:
                with io.TextIOWrapper(process.stdout, encoding="utf-8", newline="") as stream:
                    reader = csv.DictReader(stream)
                    if not reader.fieldnames:
                        raise ValueError(f"MDB sin encabezados: {member}")
                    reader.fieldnames = [name.strip().upper() for name in reader.fieldnames]
                    missing = set(LEGACY_COLUMNS).difference(reader.fieldnames)
                    extra = set(reader.fieldnames).difference(LEGACY_COLUMNS)
                    if missing or extra or len(reader.fieldnames) != len(LEGACY_COLUMNS):
                        raise ValueError(f"Esquema MDB inesperado en {member}: faltan {sorted(missing)}, sobran {sorted(extra)}")
                    yield reader
                if process.wait() != 0:
                    errors.seek(0)
                    raise ValueError(f"mdb-export falló en {member}: {errors.read()[-2000:]}")
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait()

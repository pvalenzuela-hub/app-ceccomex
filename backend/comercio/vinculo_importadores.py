"""Link each month's DIN NUM_UNICO_IMPORTADOR to an importer using the sector reports of that same month."""

from collections import defaultdict

from django.db import transaction
from django.db.models import Count

from comercio.models import Importacion
from comercio.processing import din_importers_by_number, report_month

# DIN positions of the acceptance date and the item CIF; sector reports copy both from the DIN line.
FECACEP = 39
CIF_ITEM = 158


def _monto(value):
    text = str(value or "").strip()
    text = text.replace(".", "").replace(",", ".") if "," in text and "." in text else text.replace(",", ".")
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def _fecha(value):
    digits = str(value or "").split(".")[0].strip()
    return digits.zfill(8) if digits.isdigit() else ""


def _claves_por_empresa(periodo_anio, periodo_mes, con_rut_real=True):
    """{(rut, dv): (importer, {(date, tariff, item CIF)})} of the report rows of one month."""
    from reportes.models import ReporteSectorialDetalle

    rows = ReporteSectorialDetalle.objects.filter(reporte__periodo_anio=periodo_anio, importador_probable__isnull=False).exclude(rut="")
    rows = rows.exclude(dv="") if con_rut_real else rows.filter(dv="")
    empresas = {}
    for row in rows.select_related("importador_probable").order_by("id"):
        if report_month(row.payload_json.get("MES")) != periodo_mes:
            continue
        fecha, cif = _fecha(row.payload_json.get("FECHA")), _monto(row.valor_cif)
        if fecha and cif is not None and row.partida_arancelaria_codigo:
            clave = (fecha, "".join(filter(str.isdigit, row.partida_arancelaria_codigo)), cif)
            empresas.setdefault((row.rut, row.dv), (row.importador_probable, set()))[1].add(clave)
    return empresas


def numeros_por_empresa(periodo_anio, periodo_mes, con_rut_real=True):
    """{(rut, dv): (importer, {numbers holding every report row of that company})}."""
    empresas = _claves_por_empresa(periodo_anio, periodo_mes, con_rut_real)
    buscadas = set().union(*(claves for _, claves in empresas.values())) if empresas else set()
    numeros_por_clave = defaultdict(set)
    filas = Importacion.objects.filter(
        periodo_anio=periodo_anio, periodo_mes=periodo_mes, partida_arancelaria_codigo__in={clave[1] for clave in buscadas},
    ).values_list("numero_ident", "partida_arancelaria_codigo", "payload_json")
    for numero, partida, payload in filas.iterator(chunk_size=2000):
        raw = payload.get("raw_columns", [])
        if len(raw) > CIF_ITEM:
            clave = (_fecha(raw[FECACEP]), partida, _monto(raw[CIF_ITEM]))
            if clave in buscadas:
                numeros_por_clave[clave].add(numero)
    return {
        empresa: (importador, set.intersection(*(numeros_por_clave[clave] for clave in claves)))
        for empresa, (importador, claves) in empresas.items()
    }


def importadores_del_mes(periodo_anio, periodo_mes):
    """Number -> importer. Reports that list the number itself win over a match; ambiguous matches are dropped."""
    candidatos = defaultdict(set)
    importadores = {}
    for importador, numeros in numeros_por_empresa(periodo_anio, periodo_mes).values():
        if len(numeros) == 1:
            numero = next(iter(numeros))
            candidatos[numero].add(importador.id)
            importadores[numero] = importador
    vinculos = {numero: importadores[numero] for numero, ids in candidatos.items() if len(ids) == 1}
    vinculos.update(din_importers_by_number(periodo_anio, periodo_mes))
    return vinculos


def recalcular_periodo(periodo_anio, periodo_mes, aplicar=True):
    """Set the suggested importer of one DIN month and return what changed."""
    vinculos = importadores_del_mes(periodo_anio, periodo_mes)
    filas = Importacion.objects.filter(periodo_anio=periodo_anio, periodo_mes=periodo_mes)
    con_sugerencia = filas.exclude(importador_probable_sugerido=None)
    actuales = con_sugerencia.count()
    quitar = con_sugerencia.exclude(numero_ident__in=vinculos)

    quedan = cambian = 0
    por_asignar = defaultdict(list)
    existentes = filas.filter(numero_ident__in=vinculos).values("numero_ident", "importador_probable_sugerido_id").annotate(total=Count("id"))
    for fila in existentes:
        quedan += fila["total"]
        importador_id = vinculos[fila["numero_ident"]].id
        if fila["importador_probable_sugerido_id"] != importador_id:
            cambian += fila["total"]
            por_asignar[importador_id].append(fila["numero_ident"])
    resumen = {
        "filas": filas.count(), "actuales": actuales, "quedan": quedan, "quitar": quitar.count(),
        "asignar": cambian, "numeros": len(vinculos),
    }
    if aplicar:
        with transaction.atomic():
            quitar.update(importador_probable_sugerido=None)
            for importador_id, numeros in por_asignar.items():
                filas.filter(numero_ident__in=numeros).update(importador_probable_sugerido_id=importador_id)
    return resumen

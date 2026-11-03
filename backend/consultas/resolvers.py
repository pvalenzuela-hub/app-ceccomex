from django.core.cache import cache
from django.db.models import Q

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from comercio.models import Importacion
from reportes.views import codigo_din_sql

# Reading the codes of every month from payload_json is slow and the screen asks after each search.
PENDIENTES_CACHE_SEGUNDOS = 600
PENDIENTES_PERIODOS = 3


def resolve_catalogo(grupo: str, codigo: str) -> dict:
    if not codigo:
        return {"codigo": "", "glosa": "", "vigente": False, "pendiente_revision": True}

    grupo_lookup = "comunas" if grupo == "comunas" else grupo
    item = CatalogoCodigo.objects.filter(grupo=grupo_lookup, codigo=codigo).first()
    if item:
        return {
            "codigo": item.codigo,
            "glosa": item.glosa,
            "vigente": item.vigente,
            "pendiente_revision": item.pendiente_revision,
        }

    partida = PartidaArancelaria.objects.filter(codigo=codigo).first() if grupo == "partidas" else None
    if partida:
        return {
            "codigo": partida.codigo,
            "glosa": partida.glosa,
            "vigente": partida.vigente,
            "pendiente_revision": False,
        }

    return {"codigo": codigo, "glosa": "", "vigente": False, "pendiente_revision": True}


def pendientes_importaciones(limit: int = 100) -> list[dict]:
    return cache.get_or_set(f"pendientes_importaciones_{limit}", lambda: _pendientes_importaciones(limit), PENDIENTES_CACHE_SEGUNDOS)


def _pendientes_importaciones(limit: int) -> list[dict]:
    pendientes = []
    # New codes arrive with new loads; every month adds seconds to this scan.
    periodos = Importacion.objects.order_by("-periodo_anio", "-periodo_mes").values_list("periodo_anio", "periodo_mes").distinct()[:PENDIENTES_PERIODOS]
    recientes = Q(pk__in=[])
    for anio, mes in periodos:
        recientes |= Q(periodo_anio=anio, periodo_mes=mes)
    for field_name, grupo in [
        ("aduana_codigo", "aduanas"),
        ("comuna_importador_codigo", "comunas"),
        ("pais_origen_codigo", "paises"),
        ("via_transporte_codigo", "via_transporte"),
        ("partida_arancelaria_codigo", "partidas"),
    ]:
        values = (
            Importacion.objects.filter(recientes)
            .annotate(_codigo=codigo_din_sql(field_name))
            .exclude(_codigo="")
            .values_list("_codigo", flat=True)
            .distinct()
        )
        conocidos = set(CatalogoCodigo.objects.filter(grupo=grupo, pendiente_revision=False).values_list("codigo", flat=True))
        if grupo == "partidas":
            conocidos |= set(PartidaArancelaria.objects.values_list("codigo", flat=True))
        for codigo in values:
            if codigo in conocidos:
                continue
            resolved = resolve_catalogo(grupo, codigo)
            if resolved["pendiente_revision"]:
                pendientes.append({"campo": field_name, **resolved})
                if len(pendientes) >= limit:
                    return pendientes
    return pendientes

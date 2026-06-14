from catalogos.models import CatalogoCodigo, PartidaArancelaria
from comercio.models import Importacion


def resolve_catalogo(grupo: str, codigo: str) -> dict:
    if not codigo:
        return {"codigo": "", "glosa": "", "vigente": False, "pendiente_revision": True}

    item = CatalogoCodigo.objects.filter(grupo=grupo, codigo=codigo).first()
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
    pendientes = []
    for field_name, grupo in [
        ("aduana_codigo", "aduanas"),
        ("pais_origen_codigo", "paises"),
        ("via_transporte_codigo", "via_transporte"),
        ("partida_arancelaria_codigo", "partidas"),
    ]:
        values = (
            Importacion.objects.exclude(**{f"{field_name}__isnull": True})
            .exclude(**{field_name: ""})
            .values_list(field_name, flat=True)
            .distinct()
        )
        for codigo in values:
            resolved = resolve_catalogo(grupo, codigo)
            if resolved["pendiente_revision"]:
                pendientes.append({"campo": field_name, **resolved})
                if len(pendientes) >= limit:
                    return pendientes
    return pendientes

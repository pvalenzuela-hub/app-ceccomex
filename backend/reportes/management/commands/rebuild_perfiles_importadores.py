from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from reportes.models import PerfilImportador, ReporteSectorialDetalle


def normalize(value):
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def text(value):
    return " ".join(str(value or "").strip().upper().split())


def top(counter, limit=20):
    return [{"valor": value, "ocurrencias": count} for value, count in counter.most_common(limit)]


class Command(BaseCommand):
    help = "Reconstruye perfiles históricos de importadores desde reportes sectoriales cargados."

    def handle(self, *args, **options):
        profiles = defaultdict(lambda: {"names": Counter(), "aranceles": Counter(), "mercancias": Counter(), "paises": Counter(), "aduanas": Counter(), "rubros": Counter(), "periodos": [], "total": 0})
        rows = ReporteSectorialDetalle.objects.select_related("reporte", "importador_probable").exclude(rut="")
        for row in rows.iterator(chunk_size=1000):
            rut = normalize(row.rut)
            dv = normalize(row.dv)
            if not rut or not dv:
                continue
            profile = profiles[(rut, dv)]
            profile["total"] += 1
            profile["names"][text(row.importador_probable.nombre if row.importador_probable else "")] += 1
            profile["aranceles"][text(row.partida_arancelaria_codigo)] += 1
            profile["mercancias"][text(row.mercaderia)] += 1
            profile["paises"][text(row.pais_origen_nombre)] += 1
            profile["aduanas"][text(row.aduana_nombre)] += 1
            profile["rubros"][text(row.reporte.rubro)] += 1
            profile["periodos"].append((row.reporte.periodo_anio, row.reporte.periodo_mes))

        valid_ids = []
        for (rut, dv), profile in profiles.items():
            periods = sorted(profile["periodos"])
            name = profile["names"].most_common(1)[0][0]
            instance, _ = PerfilImportador.objects.update_or_create(
                rut=rut,
                dv=dv,
                defaults={
                    "nombre": name,
                    "nombre_normalizado": normalize(name),
                    "total_evidencias": profile["total"],
                    "primer_periodo_anio": periods[0][0],
                    "primer_periodo_mes": periods[0][1],
                    "ultimo_periodo_anio": periods[-1][0],
                    "ultimo_periodo_mes": periods[-1][1],
                    "aranceles_json": top(Counter({key: value for key, value in profile["aranceles"].items() if key})),
                    "mercancias_json": top(Counter({key: value for key, value in profile["mercancias"].items() if key})),
                    "paises_origen_json": top(Counter({key: value for key, value in profile["paises"].items() if key})),
                    "aduanas_json": top(Counter({key: value for key, value in profile["aduanas"].items() if key})),
                    "rubros_json": top(Counter({key: value for key, value in profile["rubros"].items() if key})),
                },
            )
            valid_ids.append(instance.id)
        PerfilImportador.objects.exclude(id__in=valid_ids).delete()
        self.stdout.write(self.style.SUCCESS(f"Perfiles reconstruidos: {len(valid_ids)} desde {rows.count()} evidencias."))

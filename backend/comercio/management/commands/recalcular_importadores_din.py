"""Recompute the importer suggested for DIN rows from the sector reports of each row's own month."""

from django.core.management.base import BaseCommand

from comercio.legacy_mdb import SOURCE_FORMAT
from comercio.models import Importacion
from comercio.vinculo_importadores import recalcular_periodo


class Command(BaseCommand):
    help = "Recalcula el importador sugerido de las filas DIN. Sin --aplicar solo informa lo que cambiaría."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Guarda los cambios; por defecto solo los informa.")

    def handle(self, *args, **options):
        periodos = Importacion.objects.order_by("periodo_anio", "periodo_mes").values_list("periodo_anio", "periodo_mes").distinct()
        for anio, mes in periodos:
            filas = Importacion.objects.filter(periodo_anio=anio, periodo_mes=mes)
            # MDB rows carry real RUTs, so their suggestion does not depend on the month.
            if filas.filter(payload_json__source_format=SOURCE_FORMAT).exists():
                self.stdout.write(f"{anio}-{mes:02d}: MDB con RUT real, se omite")
                continue
            resumen = recalcular_periodo(anio, mes, aplicar=options["aplicar"])
            self.stdout.write(
                f"{anio}-{mes:02d}: {resumen['filas']} filas; con sugerencia {resumen['actuales']} -> {resumen['quedan']}; "
                f"sin respaldo {resumen['quitar']}; a asignar {resumen['asignar']}; importadores {resumen['numeros']}"
            )

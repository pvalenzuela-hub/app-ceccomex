"""Recompute the importer suggested for DIN rows from the sector reports of each row's own month."""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from comercio.legacy_mdb import SOURCE_FORMAT
from comercio.models import Importacion
from comercio.processing import din_importers_by_number


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
            self.recalcular(anio, mes, filas, options["aplicar"])

    def recalcular(self, anio, mes, filas, aplicar):
        numeros_por_importador = defaultdict(list)
        for numero, importador in din_importers_by_number(anio, mes).items():
            numeros_por_importador[importador.id].append(numero)
        numeros = [numero for grupo in numeros_por_importador.values() for numero in grupo]

        con_sugerencia = filas.exclude(importador_probable_sugerido=None)
        actuales = con_sugerencia.count()
        quitar = con_sugerencia.exclude(numero_ident__in=numeros)
        cambiar = {
            importador_id: filas.filter(numero_ident__in=grupo).exclude(importador_probable_sugerido_id=importador_id)
            for importador_id, grupo in numeros_por_importador.items()
        }
        total_quitar = quitar.count()
        total_cambiar = sum(consulta.count() for consulta in cambiar.values())
        quedan = filas.filter(numero_ident__in=numeros).count()
        self.stdout.write(
            f"{anio}-{mes:02d}: {filas.count()} filas; con sugerencia {actuales} -> {quedan}; "
            f"sin respaldo {total_quitar}; a asignar {total_cambiar}; importadores {len(numeros)}"
        )
        if not aplicar:
            return
        with transaction.atomic():
            quitar.update(importador_probable_sugerido=None)
            for importador_id, consulta in cambiar.items():
                consulta.update(importador_probable_sugerido_id=importador_id)

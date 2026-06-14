from pathlib import Path

from openpyxl import load_workbook
from django.core.management.base import BaseCommand

from catalogos.models import CatalogoCodigo, PartidaArancelaria


class Command(BaseCommand):
    help = "Carga catálogos base desde los xlsx de doc-req"

    def add_arguments(self, parser):
        parser.add_argument("--doc-req", dest="doc_req", default="/datos/proyectos/cec-comex-platform/doc-req")

    def handle(self, *args, **options):
        base = Path(options["doc_req"])
        tablas = base / "tablas_de_codigos(1).xlsx"
        partidas = base / "Tabla de Partidas Arancelarias(1).xlsx"

        self.load_codigo_catalogs(tablas)
        self.load_partidas(partidas)
        self.stdout.write(self.style.SUCCESS("Catálogos cargados"))

    def load_codigo_catalogs(self, path: Path):
        wb = load_workbook(path, data_only=True)
        sheet_mapping = {
            "Aduanas": (1, 2, "aduanas"),
            "Banco Comercial": (1, 2, "bancos_comerciales"),
            "Cláusulas de Compra Venta": (1, 2, "clausulas_compra_venta"),
            "Comunas": (1, 2, "comunas"),
            "Formas de pago": (1, 2, "formas_pago"),
            "Modalidades de Venta": (1, 2, "modalidades_venta"),
            "Monedas": (1, 2, "monedas"),
            "Países": (1, 2, "paises"),
            "Puertos": (1, 2, "puertos"),
            "Regiones": (1, 2, "regiones"),
            "Tipo de Bultos": (1, 2, "tipos_bulto"),
            "Tipos de carga": (1, 2, "tipos_carga"),
            "Tipos de operacion Din": (1, 2, "tipos_operacion_din"),
            "Unidads de Medida": (1, 2, "unidades_medida"),
            "Vía de transporte": (1, 2, "via_transporte"),
            "Origen de divisas": (1, 2, "origen_divisas"),
            "Vistos Buenos": (1, 2, "vistos_buenos"),
            "Régimen de Importación": (1, 2, "regimen_importacion"),
            "Claves económicas": (1, 2, "claves_economicas"),
            "Zonas económicas": (1, 2, "zonas_economicas"),
            "Claves económicas exportación": (1, 2, "claves_economicas_exportacion"),
        }
        for sheet_name, (code_col, glosa_col, grupo) in sheet_mapping.items():
            if sheet_name not in wb.sheetnames:
                continue
            ws = wb[sheet_name]
            seen = set()
            rows = []
            for row in ws.iter_rows(values_only=True):
                values = [v for v in row if v is not None]
                if len(values) < max(code_col, glosa_col):
                    continue
                codigo = str(values[code_col - 1]).strip()[:128]
                glosa = str(values[glosa_col - 1]).strip() if len(values) >= glosa_col else ""
                if not codigo or codigo.lower() == "codigo":
                    continue
                key = (grupo, codigo)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(CatalogoCodigo(grupo=grupo, codigo=codigo, glosa=glosa, origen="DOC-REQ"))
            if rows:
                CatalogoCodigo.objects.filter(grupo=grupo).delete()
                CatalogoCodigo.objects.bulk_create(rows, batch_size=1000)

    def load_partidas(self, path: Path):
        wb = load_workbook(path, data_only=True)
        ws = wb[wb.sheetnames[0]]
        rows = []
        for row in ws.iter_rows(values_only=True):
            values = [v for v in row if v is not None]
            if len(values) < 2:
                continue
            codigo = str(values[0]).strip()[:32]
            glosa = str(values[1]).strip() if len(values) > 1 else ""
            if not codigo or codigo.lower() == "codigo" or glosa.lower() == "glosa":
                continue
            rows.append(PartidaArancelaria(codigo=codigo, glosa=glosa, origen="DOC-REQ"))
        if rows:
            PartidaArancelaria.objects.all().delete()
            PartidaArancelaria.objects.bulk_create(rows, batch_size=1000)

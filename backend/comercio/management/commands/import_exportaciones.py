"""Validate or load monthly DUS export TXT files (base, bultos, documentos de transporte) from ZIP archives."""

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError

from comercio.export_loader import export_members, load_member, read_member


class Command(BaseCommand):
    help = "Valida o carga exportaciones DUS mensuales desde uno o más ZIP con los TXT de Aduana."

    def add_arguments(self, parser):
        parser.add_argument("zip_paths", nargs="+", type=Path)
        parser.add_argument("--validate-only", action="store_true")
        parser.add_argument("--replace", action="store_true", help="Reemplaza registros existentes del mismo tipo y período.")
        parser.add_argument("--batch-size", type=int, default=1000)

    def handle(self, *args, **options):
        if not 1 <= options["batch_size"] <= 5000:
            raise CommandError("--batch-size debe estar entre 1 y 5000")
        for zip_path in options["zip_paths"]:
            if not zip_path.is_file():
                raise CommandError(f"No existe: {zip_path}")
        try:
            for zip_path in options["zip_paths"]:
                with ZipFile(zip_path) as archive:
                    members = export_members(archive)
                    if not members:
                        raise ValueError(f"{zip_path.name}: no contiene TXT de exportaciones reconocibles")
                    for member, tipo in members:
                        if options["validate_only"]:
                            periodo, summary = read_member(archive, member, tipo)
                        else:
                            periodo, summary = load_member(
                                archive, member, tipo,
                                archivo_path=f"cargas/{zip_path.name}",
                                replace=options["replace"],
                                batch_size=options["batch_size"],
                                log=self.stdout.write,
                            )
                        self.stdout.write(f"{tipo} {periodo[1]:02d}/{periodo[0]} {member}: {dict(summary)}")
        except (OSError, ValueError, BadZipFile) as exc:
            raise CommandError(str(exc)) from exc

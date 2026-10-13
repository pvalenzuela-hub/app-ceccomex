from django.db import migrations


def replace_mdb_columns(apps, schema_editor):
    """Rubros saved with the former "MDB 2015 - X" columns now use the DIN-format column of the same data."""
    from reportes.views import LEGACY_COLUMN_ALIASES

    RubroImportacion = apps.get_model("reportes", "RubroImportacion")
    for rubro in RubroImportacion.objects.filter(tipo="IMP"):
        columnas = rubro.configuracion_json.get("columnas", [])
        if any(key.startswith("mdb:") for key in columnas):
            rubro.configuracion_json["columnas"] = list(dict.fromkeys(
                LEGACY_COLUMN_ALIASES.get(key, key) for key in columnas if key in LEGACY_COLUMN_ALIASES or not key.startswith("mdb:")
            ))
            rubro.save(update_fields=["configuracion_json"])


class Migration(migrations.Migration):
    dependencies = [("reportes", "0006_rubro_tipo")]

    operations = [migrations.RunPython(replace_mdb_columns, migrations.RunPython.noop)]

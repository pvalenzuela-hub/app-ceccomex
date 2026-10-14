from django.db import migrations

# Columns whose label pointed at the wrong DIN position (e.g. "CANT_MERC" read ARANC-ALA) now point at the
# field the label named; "Mercancía" repeated MERCADERIA (DNOMBRE).
RENAMES = {
    "raw:61": "raw:59", "raw:63": "raw:61", "raw:73": "raw:71", "raw:146": "raw:142", "raw:148": "raw:144",
    "raw:149": "raw:145", "raw:160": "raw:159", "glosa_mercancia": "raw:133",
}


def fix_columns(apps, schema_editor):
    RubroImportacion = apps.get_model("reportes", "RubroImportacion")
    for rubro in RubroImportacion.objects.filter(tipo="IMP"):
        columnas = rubro.configuracion_json.get("columnas", [])
        nuevas = list(dict.fromkeys(RENAMES.get(key, key) for key in columnas))
        if nuevas != columnas:
            rubro.configuracion_json["columnas"] = nuevas
            rubro.save(update_fields=["configuracion_json"])


class Migration(migrations.Migration):
    dependencies = [("reportes", "0008_rubros_cif_item")]

    operations = [migrations.RunPython(fix_columns, migrations.RunPython.noop)]

from django.db import migrations


def replace_valor_cif(apps, schema_editor):
    """"Valor CIF" is now "CIF Item" (DIN CIF-ITEM); the DIN total stays available as "CIF Total"."""
    RubroImportacion = apps.get_model("reportes", "RubroImportacion")
    for rubro in RubroImportacion.objects.filter(tipo="IMP"):
        columnas = rubro.configuracion_json.get("columnas", [])
        if "valor_cif" in columnas:
            rubro.configuracion_json["columnas"] = list(dict.fromkeys("raw:158" if key == "valor_cif" else key for key in columnas))
            rubro.save(update_fields=["configuracion_json"])


class Migration(migrations.Migration):
    dependencies = [("reportes", "0007_rubros_sin_columnas_mdb")]

    operations = [migrations.RunPython(replace_valor_cif, migrations.RunPython.noop)]

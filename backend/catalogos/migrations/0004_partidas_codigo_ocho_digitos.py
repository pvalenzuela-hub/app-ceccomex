from django.db import migrations


def pad_codes(apps, schema_editor):
    """The tariff table was loaded from Excel integers, dropping leading zeros (chapters 00-09)."""
    PartidaArancelaria = apps.get_model("catalogos", "PartidaArancelaria")
    for partida in PartidaArancelaria.objects.filter(codigo__regex=r"^[0-9]{1,7}$"):
        partida.codigo = partida.codigo.zfill(8)
        partida.save(update_fields=["codigo"])


def unpad_codes(apps, schema_editor):
    PartidaArancelaria = apps.get_model("catalogos", "PartidaArancelaria")
    for partida in PartidaArancelaria.objects.filter(codigo__regex=r"^0[0-9]{7}$"):
        partida.codigo = str(int(partida.codigo))
        partida.save(update_fields=["codigo"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalogos", "0003_alter_catalogocodigo_glosa_and_more"),
    ]

    operations = [migrations.RunPython(pad_codes, unpad_codes)]

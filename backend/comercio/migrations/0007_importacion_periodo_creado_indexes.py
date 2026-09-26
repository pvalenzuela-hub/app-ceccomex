from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("comercio", "0006_importacion_importador_probable_sugerido"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="importacion",
            index=models.Index(fields=["periodo_anio", "periodo_mes", "-creado"], name="imp_periodo_creado_idx"),
        ),
        migrations.AddIndex(
            model_name="importacion",
            index=models.Index(fields=["-creado"], name="imp_creado_idx"),
        ),
    ]

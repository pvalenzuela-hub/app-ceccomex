from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("comercio", "0005_importacion_comuna_importador_codigo"), ("reportes", "0002_reportesectorial_es_acumulado")]

    operations = [
        migrations.AddField(
            model_name="importacion",
            name="importador_probable_sugerido",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="importaciones_sugeridas", to="reportes.importadorprobable"),
        ),
    ]

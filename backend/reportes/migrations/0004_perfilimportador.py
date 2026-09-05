from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reportes", "0003_rubroimportacion")]

    operations = [
        migrations.CreateModel(
            name="PerfilImportador",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rut", models.CharField(max_length=16)),
                ("dv", models.CharField(max_length=4)),
                ("nombre", models.CharField(max_length=255)),
                ("nombre_normalizado", models.CharField(max_length=255)),
                ("total_evidencias", models.PositiveIntegerField(default=0)),
                ("primer_periodo_anio", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("primer_periodo_mes", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("ultimo_periodo_anio", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("ultimo_periodo_mes", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("aranceles_json", models.JSONField(default=list)),
                ("mercancias_json", models.JSONField(default=list)),
                ("paises_origen_json", models.JSONField(default=list)),
                ("aduanas_json", models.JSONField(default=list)),
                ("rubros_json", models.JSONField(default=list)),
                ("actualizado", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["nombre"], "unique_together": {("rut", "dv")}},
        ),
    ]

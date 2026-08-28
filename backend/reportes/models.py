from django.db import models


class ImportadorProbable(models.Model):
    rut = models.CharField(max_length=16, blank=True)
    dv = models.CharField(max_length=4, blank=True)
    nombre = models.CharField(max_length=255)
    origen = models.CharField(max_length=32, default="REPORTE_SECTORIAL")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("rut", "dv", "nombre")
        ordering = ["nombre"]


class ReporteSectorial(models.Model):
    nombre_archivo = models.CharField(max_length=255)
    rubro = models.CharField(max_length=128)
    periodo_anio = models.PositiveSmallIntegerField()
    periodo_mes = models.PositiveSmallIntegerField()
    hoja_base = models.CharField(max_length=128)
    es_acumulado = models.BooleanField(default=False)
    ruta_origen = models.TextField()
    total_registros = models.PositiveIntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("nombre_archivo", "hoja_base")
        ordering = ["-periodo_anio", "-periodo_mes", "rubro"]


class ReporteSectorialDetalle(models.Model):
    reporte = models.ForeignKey(ReporteSectorial, on_delete=models.CASCADE, related_name="detalles")
    nro_linea = models.PositiveIntegerField()
    importador_probable = models.ForeignKey(ImportadorProbable, null=True, blank=True, on_delete=models.SET_NULL, related_name="referencias")
    rut = models.CharField(max_length=16, blank=True)
    dv = models.CharField(max_length=4, blank=True)
    aduana_nombre = models.CharField(max_length=128, blank=True)
    pais_origen_nombre = models.CharField(max_length=128, blank=True)
    partida_arancelaria_codigo = models.CharField(max_length=32, blank=True)
    mercaderia = models.TextField(blank=True)
    valor_fob = models.CharField(max_length=32, blank=True)
    valor_flete = models.CharField(max_length=32, blank=True)
    valor_seguro = models.CharField(max_length=32, blank=True)
    valor_cif = models.CharField(max_length=32, blank=True)
    payload_json = models.JSONField(default=dict)

    class Meta:
        unique_together = ("reporte", "nro_linea")
        ordering = ["nro_linea"]

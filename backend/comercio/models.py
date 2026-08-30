from django.db import models


class ArchivoCarga(models.Model):
    TIPO_CHOICES = [
        ("IMP", "Importaciones"),
        ("EXP_BASE", "Exportaciones Base"),
        ("EXP_BULTO", "Exportaciones Bultos"),
        ("EXP_DOC", "Exportaciones Documentos de Transporte"),
    ]

    ESTADO_CHOICES = [
        ("PENDIENTE", "Pendiente"),
        ("PROCESANDO", "Procesando"),
        ("PROCESADO", "Procesado"),
        ("ERROR", "Error"),
    ]

    nombre_archivo = models.CharField(max_length=255)
    archivo = models.FileField(upload_to="cargas/")
    tipo_archivo = models.CharField(max_length=16, choices=TIPO_CHOICES)
    estado = models.CharField(max_length=32, choices=ESTADO_CHOICES, default="PENDIENTE")
    periodo_anio = models.PositiveSmallIntegerField(null=True, blank=True)
    periodo_mes = models.PositiveSmallIntegerField(null=True, blank=True)
    total_registros = models.PositiveIntegerField(default=0)
    total_procesados = models.PositiveIntegerField(default=0)
    total_ok = models.PositiveIntegerField(default=0)
    total_error = models.PositiveIntegerField(default=0)
    observacion = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)


class ArchivoCargaStaging(models.Model):
    archivo_carga = models.ForeignKey(ArchivoCarga, on_delete=models.CASCADE, related_name="staging")
    nro_linea = models.PositiveIntegerField()
    raw_line = models.TextField()
    data_json = models.JSONField(default=dict)
    procesado = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nro_linea"]
        unique_together = ("archivo_carga", "nro_linea")


class Importacion(models.Model):
    archivo_origen = models.ForeignKey(ArchivoCarga, on_delete=models.CASCADE, related_name="importaciones")
    periodo_anio = models.PositiveSmallIntegerField(null=True, blank=True)
    periodo_mes = models.PositiveSmallIntegerField(null=True, blank=True)
    numero_ident = models.CharField(max_length=64, blank=True)
    importador_probable_sugerido = models.ForeignKey("reportes.ImportadorProbable", null=True, blank=True, on_delete=models.SET_NULL, related_name="importaciones_sugeridas")
    item = models.CharField(max_length=32, blank=True)
    fecha_text = models.CharField(max_length=32, blank=True)
    fecha_date = models.DateField(null=True, blank=True)
    aduana_codigo = models.CharField(max_length=32, blank=True)
    comuna_importador_codigo = models.CharField(max_length=32, blank=True)
    pais_origen_codigo = models.CharField(max_length=32, blank=True)
    via_transporte_codigo = models.CharField(max_length=32, blank=True)
    partida_arancelaria_codigo = models.CharField(max_length=32, blank=True)
    glosa_mercancia = models.TextField(blank=True)
    valor_fob = models.CharField(max_length=32, blank=True)
    valor_flete = models.CharField(max_length=32, blank=True)
    valor_seguro = models.CharField(max_length=32, blank=True)
    valor_cif = models.CharField(max_length=32, blank=True)
    payload_json = models.JSONField(default=dict)
    creado = models.DateTimeField(auto_now_add=True)


class Exportacion(models.Model):
    archivo_origen = models.ForeignKey(ArchivoCarga, on_delete=models.CASCADE, related_name="exportaciones")
    periodo_anio = models.PositiveSmallIntegerField(null=True, blank=True)
    periodo_mes = models.PositiveSmallIntegerField(null=True, blank=True)
    numero_ident = models.CharField(max_length=64, blank=True)
    item = models.CharField(max_length=32, blank=True)
    fecha_text = models.CharField(max_length=32, blank=True)
    fecha_date = models.DateField(null=True, blank=True)
    aduana_codigo = models.CharField(max_length=32, blank=True)
    pais_destino_codigo = models.CharField(max_length=32, blank=True)
    via_transporte_codigo = models.CharField(max_length=32, blank=True)
    partida_arancelaria_codigo = models.CharField(max_length=32, blank=True)
    glosa_mercancia = models.TextField(blank=True)
    valor_fob = models.CharField(max_length=32, blank=True)
    payload_json = models.JSONField(default=dict)
    creado = models.DateTimeField(auto_now_add=True)


class ExportacionBulto(models.Model):
    archivo_origen = models.ForeignKey(ArchivoCarga, on_delete=models.CASCADE, related_name="bultos")
    periodo_anio = models.PositiveSmallIntegerField(null=True, blank=True)
    periodo_mes = models.PositiveSmallIntegerField(null=True, blank=True)
    numero_ident = models.CharField(max_length=64, blank=True)
    secuencia = models.CharField(max_length=32, blank=True)
    tipo_bulto_codigo = models.CharField(max_length=32, blank=True)
    cantidad_bultos = models.CharField(max_length=32, blank=True)
    marcas = models.CharField(max_length=255, blank=True)
    payload_json = models.JSONField(default=dict)
    creado = models.DateTimeField(auto_now_add=True)


class ExportacionDocTransporte(models.Model):
    archivo_origen = models.ForeignKey(ArchivoCarga, on_delete=models.CASCADE, related_name="documentos_transporte")
    periodo_anio = models.PositiveSmallIntegerField(null=True, blank=True)
    periodo_mes = models.PositiveSmallIntegerField(null=True, blank=True)
    numero_ident = models.CharField(max_length=64, blank=True)
    secuencia = models.CharField(max_length=32, blank=True)
    numero_documento = models.CharField(max_length=64, blank=True)
    fecha_documento_text = models.CharField(max_length=32, blank=True)
    nave = models.CharField(max_length=255, blank=True)
    numero_viaje = models.CharField(max_length=64, blank=True)
    puerto_embarque_codigo = models.CharField(max_length=32, blank=True)
    via_transporte_codigo = models.CharField(max_length=32, blank=True)
    payload_json = models.JSONField(default=dict)
    creado = models.DateTimeField(auto_now_add=True)

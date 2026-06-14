from django.contrib import admin
from comercio.models import ArchivoCarga, ArchivoCargaStaging, Exportacion, ExportacionBulto, ExportacionDocTransporte, Importacion


@admin.register(ArchivoCarga)
class ArchivoCargaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre_archivo", "tipo_archivo", "estado", "periodo_anio", "periodo_mes", "creado")
    list_filter = ("tipo_archivo", "estado", "periodo_anio", "periodo_mes")
    search_fields = ("nombre_archivo",)


@admin.register(ArchivoCargaStaging)
class ArchivoCargaStagingAdmin(admin.ModelAdmin):
    list_display = ("id", "archivo_carga", "nro_linea", "procesado", "creado")
    list_filter = ("procesado",)
    search_fields = ("raw_line",)


@admin.register(Importacion)
class ImportacionAdmin(admin.ModelAdmin):
    list_display = ("id", "archivo_origen", "numero_ident", "item", "partida_arancelaria_codigo", "creado")
    search_fields = ("numero_ident", "item", "partida_arancelaria_codigo")


@admin.register(Exportacion)
class ExportacionAdmin(admin.ModelAdmin):
    list_display = ("id", "archivo_origen", "numero_ident", "item", "partida_arancelaria_codigo", "creado")
    search_fields = ("numero_ident", "item", "partida_arancelaria_codigo")


@admin.register(ExportacionBulto)
class ExportacionBultoAdmin(admin.ModelAdmin):
    list_display = ("id", "archivo_origen", "numero_ident", "secuencia", "tipo_bulto_codigo", "creado")
    search_fields = ("numero_ident", "secuencia", "tipo_bulto_codigo")


@admin.register(ExportacionDocTransporte)
class ExportacionDocTransporteAdmin(admin.ModelAdmin):
    list_display = ("id", "archivo_origen", "numero_ident", "secuencia", "numero_documento", "creado")
    search_fields = ("numero_ident", "secuencia", "numero_documento")

from django.contrib import admin

from reportes.models import ImportadorProbable, ReporteSectorial, ReporteSectorialDetalle


@admin.register(ImportadorProbable)
class ImportadorProbableAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rut", "dv", "origen")
    search_fields = ("nombre", "rut")


@admin.register(ReporteSectorial)
class ReporteSectorialAdmin(admin.ModelAdmin):
    list_display = ("nombre_archivo", "rubro", "periodo_anio", "periodo_mes", "total_registros")
    list_filter = ("periodo_anio", "periodo_mes", "rubro")


@admin.register(ReporteSectorialDetalle)
class ReporteSectorialDetalleAdmin(admin.ModelAdmin):
    list_display = ("reporte", "nro_linea", "rut", "importador_probable", "partida_arancelaria_codigo")
    search_fields = ("rut", "partida_arancelaria_codigo", "mercaderia")

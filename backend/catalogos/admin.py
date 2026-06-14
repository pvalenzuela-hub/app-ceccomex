from django.contrib import admin

from catalogos.models import CatalogoCodigo, PartidaArancelaria


@admin.register(CatalogoCodigo)
class CatalogoCodigoAdmin(admin.ModelAdmin):
    list_display = ("grupo", "codigo", "glosa", "vigente", "origen")
    search_fields = ("grupo", "codigo", "glosa")
    list_filter = ("grupo", "vigente", "origen")


@admin.register(PartidaArancelaria)
class PartidaArancelariaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "glosa", "vigente", "origen")
    search_fields = ("codigo", "glosa")
    list_filter = ("vigente", "origen")

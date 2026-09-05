from django.urls import path

from reportes.views import detalle_reporte, exportar_informe_importaciones, importadores_probables, importaciones_configuracion, partidas_importacion, perfiles_importadores, reportes, rubro_importacion_detalle, rubros_importaciones


urlpatterns = [
    path("perfiles-importadores/", perfiles_importadores, name="perfiles-importadores"),
    path("", reportes, name="reportes-sectoriales"),
    path("<int:reporte_id>/", detalle_reporte, name="reportes-sectoriales-detalle"),
    path("importadores/", importadores_probables, name="importadores-probables"),
    path("importaciones/configuracion/", importaciones_configuracion, name="informes-importaciones-configuracion"),
    path("importaciones/partidas/", partidas_importacion, name="informes-importaciones-partidas"),
    path("importaciones/exportar/", exportar_informe_importaciones, name="informes-importaciones-exportar"),
    path("importaciones/rubros/", rubros_importaciones, name="informes-importaciones-rubros"),
    path("importaciones/rubros/<int:rubro_id>/", rubro_importacion_detalle, name="informes-importaciones-rubro"),
]

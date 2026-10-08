from django.urls import path

from reportes.exportaciones import exportaciones_configuracion, exportar_informe_exportaciones
from reportes.views import detalle_reporte, informe_descargar, informe_estado, exportar_informe_importaciones, importadores_probables, importaciones_configuracion, partidas_importacion, perfiles_importadores, reportes, rubro_importacion_detalle, rubros_importaciones


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
    path("informes/<int:informe_id>/", informe_estado, name="informe-estado"),
    path("informes/<int:informe_id>/descargar/", informe_descargar, name="informe-descargar"),
    path("exportaciones/configuracion/", exportaciones_configuracion, name="informes-exportaciones-configuracion"),
    path("exportaciones/exportar/", exportar_informe_exportaciones, name="informes-exportaciones-exportar"),
]

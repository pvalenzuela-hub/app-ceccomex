from django.urls import path

from reportes.views import detalle_reporte, importadores_probables, reportes


urlpatterns = [
    path("", reportes, name="reportes-sectoriales"),
    path("<int:reporte_id>/", detalle_reporte, name="reportes-sectoriales-detalle"),
    path("importadores/", importadores_probables, name="importadores-probables"),
]

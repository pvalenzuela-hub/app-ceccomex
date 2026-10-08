from django.urls import path

from consultas.exportaciones import exportacion_detalle, exportaciones, exportar_exportaciones
from consultas.views import exportar_importaciones, favorito_detalle, favoritos, importaciones, pendientes_revision

urlpatterns = [
    path("importaciones/", importaciones, name="consultas-importaciones"),
    path("importaciones/exportar/", exportar_importaciones, name="consultas-importaciones-exportar"),
    path("exportaciones/", exportaciones, name="consultas-exportaciones"),
    path("exportaciones/exportar/", exportar_exportaciones, name="consultas-exportaciones-exportar"),
    path("exportaciones/dus/<str:numero_ident>/", exportacion_detalle, name="consultas-exportacion-detalle"),
    path("pendientes-revision/", pendientes_revision, name="consultas-pendientes-revision"),
    path("favoritos/", favoritos, name="consultas-favoritos"),
    path("favoritos/<int:favorito_id>/", favorito_detalle, name="consultas-favorito-detalle"),
]

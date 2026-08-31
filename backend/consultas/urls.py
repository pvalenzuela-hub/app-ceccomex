from django.urls import path

from consultas.views import exportar_importaciones, favorito_detalle, favoritos, importaciones, pendientes_revision

urlpatterns = [
    path("importaciones/", importaciones, name="consultas-importaciones"),
    path("importaciones/exportar/", exportar_importaciones, name="consultas-importaciones-exportar"),
    path("pendientes-revision/", pendientes_revision, name="consultas-pendientes-revision"),
    path("favoritos/", favoritos, name="consultas-favoritos"),
    path("favoritos/<int:favorito_id>/", favorito_detalle, name="consultas-favorito-detalle"),
]

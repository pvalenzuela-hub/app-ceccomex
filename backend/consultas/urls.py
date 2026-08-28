from django.urls import path

from consultas.views import exportar_importaciones, importaciones, pendientes_revision

urlpatterns = [
    path("importaciones/", importaciones, name="consultas-importaciones"),
    path("importaciones/exportar/", exportar_importaciones, name="consultas-importaciones-exportar"),
    path("pendientes-revision/", pendientes_revision, name="consultas-pendientes-revision"),
]

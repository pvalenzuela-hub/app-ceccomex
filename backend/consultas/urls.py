from django.urls import path

from consultas.views import importaciones, pendientes_revision

urlpatterns = [
    path("importaciones/", importaciones, name="consultas-importaciones"),
    path("pendientes-revision/", pendientes_revision, name="consultas-pendientes-revision"),
]

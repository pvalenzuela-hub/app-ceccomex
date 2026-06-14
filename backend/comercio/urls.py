from django.urls import path
from comercio.views import list_archivos, list_staging, upload_archivo

urlpatterns = [
    path("upload/", upload_archivo, name="upload-archivo"),
    path("archivos/", list_archivos, name="list-archivos"),
    path("archivos/<int:archivo_id>/staging/", list_staging, name="list-staging"),
]

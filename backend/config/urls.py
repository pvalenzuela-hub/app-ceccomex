from django.contrib import admin
from django.urls import include, path

from core.views import health_check, system_metrics


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/core/metrics/", system_metrics, name="system-metrics"),
    path("api/core/", include("core.urls")),
    path("api/catalogos/", include("catalogos.urls")),
    path("api/comercio/", include("comercio.urls")),
    path("api/consultas/", include("consultas.urls")),
]

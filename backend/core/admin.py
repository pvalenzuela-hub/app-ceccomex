from django.contrib import admin

# Admin registration will grow with the domain models.

from core.models import RegistroActividad


@admin.register(RegistroActividad)
class RegistroActividadAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario_nombre", "accion", "modulo", "ip")
    list_filter = ("accion", "modulo")
    search_fields = ("usuario_nombre",)

from django.db import models


class AuditMixin(models.Model):
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PresenciaUsuario(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    session_key = models.CharField(max_length=64, unique=True)
    last_seen = models.DateTimeField(auto_now=True)


class RegistroActividad(models.Model):
    """One row per meaningful action, to know how the platform is used."""

    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    # Kept as text so the log survives a deleted user and records the name typed in a failed login.
    usuario_nombre = models.CharField(max_length=150, blank=True)
    accion = models.CharField(max_length=40, db_index=True)
    modulo = models.CharField(max_length=30, blank=True)
    detalle = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]

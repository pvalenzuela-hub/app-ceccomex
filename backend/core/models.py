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

from django.db import models


class ConsultaGuardada(models.Model):
    nombre = models.CharField(max_length=120)
    filtros_json = models.JSONField(default=dict)
    creado = models.DateTimeField(auto_now_add=True)

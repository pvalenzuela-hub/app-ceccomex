from django.db import models


class CatalogoBase(models.Model):
    codigo = models.CharField(max_length=128)
    glosa = models.TextField(blank=True)
    vigente = models.BooleanField(default=True)
    origen = models.CharField(max_length=32, default="INICIAL")
    pendiente_revision = models.BooleanField(default=False)
    observacion = models.TextField(blank=True)

    class Meta:
        abstract = True


class CatalogoCodigo(CatalogoBase):
    grupo = models.CharField(max_length=96)

    class Meta:
        verbose_name = "Catálogo de código"
        verbose_name_plural = "Catálogos de códigos"
        unique_together = ("grupo", "codigo")


class PartidaArancelaria(models.Model):
    codigo = models.CharField(max_length=32, unique=True)
    glosa = models.TextField()
    vigente = models.BooleanField(default=True)
    origen = models.CharField(max_length=32, default="INICIAL")
    observacion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Partida arancelaria"
        verbose_name_plural = "Partidas arancelarias"

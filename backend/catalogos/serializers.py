from rest_framework import serializers

from catalogos.models import CatalogoCodigo, PartidaArancelaria


class CatalogoCodigoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogoCodigo
        fields = ("id", "grupo", "codigo", "glosa", "vigente", "origen", "pendiente_revision", "observacion")


class PartidaArancelariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartidaArancelaria
        fields = ("id", "codigo", "glosa", "vigente", "origen", "observacion")

from rest_framework import serializers

from catalogos.models import CatalogoCodigo, PartidaArancelaria


class CatalogoCodigoSerializer(serializers.ModelSerializer):
    def update(self, instance, validated_data):
        # A code keeps its catalog group; moving it would break resolver lookups.
        validated_data.pop("grupo", None)
        return super().update(instance, validated_data)

    class Meta:
        model = CatalogoCodigo
        fields = ("id", "grupo", "codigo", "glosa", "vigente", "origen", "pendiente_revision", "observacion")


class PartidaArancelariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartidaArancelaria
        fields = ("id", "codigo", "glosa", "vigente", "origen", "observacion")

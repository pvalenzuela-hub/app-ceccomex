from rest_framework import serializers

from catalogos.models import CatalogoCodigo, PartidaArancelaria


class CatalogoCodigoSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        vigente = attrs.get("vigente", self.instance.vigente if self.instance else True)
        pendiente = attrs.get("pendiente_revision", self.instance.pendiente_revision if self.instance else False)
        if vigente == pendiente:
            raise serializers.ValidationError("El estado debe ser Vigente o Pendiente de revisión.")
        return attrs

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

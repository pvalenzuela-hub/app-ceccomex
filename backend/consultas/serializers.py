from rest_framework import serializers

from comercio.models import Importacion


class ImportacionConsultaSerializer(serializers.ModelSerializer):
    aduana = serializers.SerializerMethodField()
    comuna_importador = serializers.SerializerMethodField()
    pais_origen = serializers.SerializerMethodField()
    partida = serializers.SerializerMethodField()

    class Meta:
        model = Importacion
        fields = [
            "id",
            "archivo_origen",
            "periodo_anio",
            "periodo_mes",
            "numero_ident",
            "item",
            "fecha_text",
            "aduana_codigo",
            "comuna_importador_codigo",
            "pais_origen_codigo",
            "via_transporte_codigo",
            "partida_arancelaria_codigo",
            "aduana",
            "comuna_importador",
            "pais_origen",
            "partida",
            "glosa_mercancia",
            "valor_fob",
            "valor_flete",
            "valor_seguro",
            "valor_cif",
            "creado",
        ]

    def get_aduana(self, obj):
        return self.context.get("resolver")("aduanas", obj.aduana_codigo) if self.context.get("resolver") else {"codigo": obj.aduana_codigo, "glosa": "", "pendiente_revision": True}

    def get_comuna_importador(self, obj):
        return self.context.get("resolver")("comunas", obj.comuna_importador_codigo) if self.context.get("resolver") else {"codigo": obj.comuna_importador_codigo, "glosa": "", "pendiente_revision": True}

    def get_pais_origen(self, obj):
        return self.context.get("resolver")("paises", obj.pais_origen_codigo) if self.context.get("resolver") else {"codigo": obj.pais_origen_codigo, "glosa": "", "pendiente_revision": True}

    def get_partida(self, obj):
        return self.context.get("resolver")("partidas", obj.partida_arancelaria_codigo) if self.context.get("resolver") else {"codigo": obj.partida_arancelaria_codigo, "glosa": "", "pendiente_revision": True}

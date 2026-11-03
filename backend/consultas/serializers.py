from rest_framework import serializers

from comercio.descripcion import campos_descripcion
from comercio.models import Importacion
from consultas.models import ConsultaGuardada
from reportes.views import DIN_POSITIONS, _column_value, codigo_din, valor_din


def fecha_aceptacion(obj):
    return valor_din(obj, DIN_POSITIONS["FECACEP"]) or obj.fecha_text


class ImportacionConsultaSerializer(serializers.ModelSerializer):
    numero_ident = serializers.SerializerMethodField()
    item = serializers.SerializerMethodField()
    fecha_text = serializers.SerializerMethodField()
    aduana_codigo = serializers.SerializerMethodField()
    comuna_importador_codigo = serializers.SerializerMethodField()
    pais_origen_codigo = serializers.SerializerMethodField()
    via_transporte_codigo = serializers.SerializerMethodField()
    partida_arancelaria_codigo = serializers.SerializerMethodField()
    valor_fob = serializers.SerializerMethodField()
    valor_flete = serializers.SerializerMethodField()
    valor_seguro = serializers.SerializerMethodField()
    valor_cif = serializers.SerializerMethodField()
    aduana = serializers.SerializerMethodField()
    comuna_importador = serializers.SerializerMethodField()
    pais_origen = serializers.SerializerMethodField()
    partida = serializers.SerializerMethodField()
    glosa_mercancia = serializers.SerializerMethodField()

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

    def get_numero_ident(self, obj):
        return codigo_din(obj, "numero_ident")

    def get_item(self, obj):
        return codigo_din(obj, "item")

    def get_fecha_text(self, obj):
        return fecha_aceptacion(obj)

    def get_aduana_codigo(self, obj):
        return codigo_din(obj, "aduana_codigo")

    def get_comuna_importador_codigo(self, obj):
        return codigo_din(obj, "comuna_importador_codigo")

    def get_pais_origen_codigo(self, obj):
        return codigo_din(obj, "pais_origen_codigo")

    def get_via_transporte_codigo(self, obj):
        return codigo_din(obj, "via_transporte_codigo")

    def get_partida_arancelaria_codigo(self, obj):
        return codigo_din(obj, "partida_arancelaria_codigo")

    def get_valor_fob(self, obj):
        return _column_value(obj, "valor_fob", {})

    def get_valor_flete(self, obj):
        return _column_value(obj, "valor_flete", {})

    def get_valor_seguro(self, obj):
        return _column_value(obj, "valor_seguro", {})

    def get_valor_cif(self, obj):
        return _column_value(obj, f"raw:{DIN_POSITIONS['CIF-ITEM']}", {})

    def get_aduana(self, obj):
        codigo = codigo_din(obj, "aduana_codigo")
        return self.context.get("resolver")("aduanas", codigo) if self.context.get("resolver") else {"codigo": codigo, "glosa": "", "pendiente_revision": True}

    def get_comuna_importador(self, obj):
        codigo = codigo_din(obj, "comuna_importador_codigo")
        return self.context.get("resolver")("comunas", codigo) if self.context.get("resolver") else {"codigo": codigo, "glosa": "", "pendiente_revision": True}

    def get_pais_origen(self, obj):
        codigo = codigo_din(obj, "pais_origen_codigo")
        return self.context.get("resolver")("paises", codigo) if self.context.get("resolver") else {"codigo": codigo, "glosa": "", "pendiente_revision": True}

    def get_glosa_mercancia(self, obj):
        return campos_descripcion(obj.payload_json)["descripcion"][0]

    def get_partida(self, obj):
        codigo = codigo_din(obj, "partida_arancelaria_codigo")
        return self.context.get("resolver")("partidas", codigo) if self.context.get("resolver") else {"codigo": codigo, "glosa": "", "pendiente_revision": True}


class ConsultaGuardadaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultaGuardada
        fields = ("id", "nombre", "filtros_json", "creado")
        read_only_fields = ("id", "creado")

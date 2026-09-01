from rest_framework import serializers

from reportes.models import ImportadorProbable, ReporteSectorial, ReporteSectorialDetalle, RubroImportacion


class ReporteSectorialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReporteSectorial
        fields = ("id", "nombre_archivo", "rubro", "periodo_anio", "periodo_mes", "hoja_base", "es_acumulado", "total_registros", "creado")


class ReporteSectorialDetalleSerializer(serializers.ModelSerializer):
    importador_nombre = serializers.CharField(source="importador_probable.nombre", read_only=True)

    class Meta:
        model = ReporteSectorialDetalle
        fields = ("nro_linea", "rut", "dv", "importador_nombre", "aduana_nombre", "pais_origen_nombre", "partida_arancelaria_codigo", "mercaderia", "valor_fob", "valor_flete", "valor_seguro", "valor_cif")


class ImportadorProbableSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportadorProbable
        fields = ("id", "rut", "dv", "nombre", "origen")


class RubroImportacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RubroImportacion
        fields = ("id", "nombre", "configuracion_json", "creado", "actualizado")
        read_only_fields = ("id", "creado", "actualizado")

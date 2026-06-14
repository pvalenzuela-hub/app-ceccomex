from rest_framework import serializers

from comercio.models import ArchivoCarga, ArchivoCargaStaging, Exportacion, ExportacionBulto, ExportacionDocTransporte, Importacion


class ArchivoCargaSerializer(serializers.ModelSerializer):
    nombre_archivo = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = ArchivoCarga
        fields = [
            "id",
            "nombre_archivo",
            "archivo",
            "tipo_archivo",
            "estado",
            "periodo_anio",
            "periodo_mes",
            "total_registros",
            "total_procesados",
            "total_ok",
            "total_error",
            "observacion",
            "creado",
        ]
        read_only_fields = ["estado", "total_registros", "total_ok", "total_error", "creado"]

    def validate(self, attrs):
        archivo = attrs.get("archivo")
        nombre_archivo = attrs.get("nombre_archivo")
        if archivo and not nombre_archivo:
            attrs["nombre_archivo"] = archivo.name
        return attrs


class ArchivoCargaListSerializer(serializers.ModelSerializer):
    staging_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ArchivoCarga
        fields = [
            "id",
            "nombre_archivo",
            "tipo_archivo",
            "estado",
            "periodo_anio",
            "periodo_mes",
            "total_registros",
            "total_procesados",
            "staging_count",
            "total_ok",
            "total_error",
            "creado",
        ]


class ArchivoCargaStagingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArchivoCargaStaging
        fields = ["id", "archivo_carga", "nro_linea", "raw_line", "data_json", "procesado", "error", "creado"]


class ImportacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Importacion
        fields = "__all__"


class ExportacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exportacion
        fields = "__all__"


class ExportacionBultoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportacionBulto
        fields = "__all__"


class ExportacionDocTransporteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportacionDocTransporte
        fields = "__all__"

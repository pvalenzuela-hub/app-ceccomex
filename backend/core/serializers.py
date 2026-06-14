from rest_framework import serializers


class SystemMetricsSerializer(serializers.Serializer):
    cargas_totales = serializers.IntegerField()
    cargas_procesadas = serializers.IntegerField()
    cargas_procesando = serializers.IntegerField()
    importaciones_totales = serializers.IntegerField()
    consultas_guardadas = serializers.IntegerField()

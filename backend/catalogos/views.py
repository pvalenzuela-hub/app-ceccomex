from rest_framework.viewsets import ModelViewSet
from django.db.models import Q

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from catalogos.serializers import CatalogoCodigoSerializer, PartidaArancelariaSerializer


class CatalogoCodigoViewSet(ModelViewSet):
    serializer_class = CatalogoCodigoSerializer

    def get_queryset(self):
        queryset = CatalogoCodigo.objects.all().order_by("grupo", "codigo")
        grupo = self.request.query_params.get("grupo", "").strip()
        search = self.request.query_params.get("search", "").strip()
        if grupo:
            queryset = queryset.filter(grupo__iexact=grupo)
        if search:
            queryset = queryset.filter(Q(codigo__icontains=search) | Q(glosa__icontains=search))
        return queryset


class PartidaArancelariaViewSet(ModelViewSet):
    serializer_class = PartidaArancelariaSerializer
    queryset = PartidaArancelaria.objects.all().order_by("codigo")

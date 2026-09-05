from rest_framework.viewsets import ModelViewSet
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from catalogos.serializers import CatalogoCodigoSerializer, PartidaArancelariaSerializer


class CatalogPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class CatalogoCodigoViewSet(ModelViewSet):
    serializer_class = CatalogoCodigoSerializer
    pagination_class = CatalogPagination

    def get_permissions(self):
        permission_class = AllowAny if self.action in ("list", "retrieve") else IsAuthenticated
        return [permission_class()]

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
    pagination_class = CatalogPagination

    def get_permissions(self):
        permission_class = AllowAny if self.action in ("list", "retrieve") else IsAuthenticated
        return [permission_class()]

    def get_queryset(self):
        queryset = PartidaArancelaria.objects.all().order_by("codigo")
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(codigo__istartswith=search) | Q(glosa__icontains=search))
        return queryset

from rest_framework.viewsets import ModelViewSet
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination

from catalogos.models import CatalogoCodigo, PartidaArancelaria
from catalogos.serializers import CatalogoCodigoSerializer, PartidaArancelariaSerializer
from core.actividad import registrar


class RegistroCambiosMixin:
    """Logs every change to a catalog row."""

    tabla = ""

    def _registrar(self, accion, instance):
        registro = " ".join(str(getattr(instance, campo, "")) for campo in ("grupo", "codigo", "glosa")).strip()
        registrar(self.request, accion, "catalogos", tabla=self.tabla, registro=registro[:200])

    def perform_create(self, serializer):
        self._registrar("catalogo_creado", serializer.save())

    def perform_update(self, serializer):
        self._registrar("catalogo_modificado", serializer.save())

    def perform_destroy(self, instance):
        self._registrar("catalogo_eliminado", instance)
        instance.delete()


class CatalogPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class CatalogoCodigoViewSet(RegistroCambiosMixin, ModelViewSet):
    tabla = "Códigos"
    serializer_class = CatalogoCodigoSerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = CatalogoCodigo.objects.all().order_by("grupo", "codigo")
        grupo = self.request.query_params.get("grupo", "").strip()
        search = self.request.query_params.get("search", "").strip()
        if grupo:
            queryset = queryset.filter(grupo__iexact=grupo)
        if search:
            queryset = queryset.filter(Q(codigo__icontains=search) | Q(glosa__icontains=search))
        return queryset


class PartidaArancelariaViewSet(RegistroCambiosMixin, ModelViewSet):
    tabla = "Partidas arancelarias"
    serializer_class = PartidaArancelariaSerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = PartidaArancelaria.objects.all().order_by("codigo")
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(codigo__istartswith=search) | Q(glosa__icontains=search))
        return queryset

from rest_framework.routers import DefaultRouter

from catalogos.views import CatalogoCodigoViewSet, PartidaArancelariaViewSet


router = DefaultRouter()
router.register("codigos", CatalogoCodigoViewSet, basename="catalogo-codigo")
router.register("partidas", PartidaArancelariaViewSet, basename="partida-arancelaria")

urlpatterns = router.urls

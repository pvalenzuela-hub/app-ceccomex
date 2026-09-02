from django.urls import path

from core.views import health_check, login_check, logout_view, usuarios


urlpatterns = [path("health/", health_check, name="core-health")]
urlpatterns += [path("login-check/", login_check, name="login-check")]
urlpatterns += [path("logout/", logout_view, name="logout")]
urlpatterns += [path("usuarios/", usuarios, name="usuarios")]

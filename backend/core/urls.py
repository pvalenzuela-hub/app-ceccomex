from django.urls import path

from core.views import health_check, login_check, logout_view, session_user, usuarios


urlpatterns = [path("health/", health_check, name="core-health")]
urlpatterns += [path("login-check/", login_check, name="login-check")]
urlpatterns += [path("logout/", logout_view, name="logout")]
urlpatterns += [path("sesion/", session_user, name="session-user")]
urlpatterns += [path("usuarios/", usuarios, name="usuarios")]

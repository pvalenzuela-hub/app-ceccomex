from django.urls import path

from core.views import cambiar_contrasena_usuario, eliminar_usuario, health_check, login_check, logout_view, presencia, session_user, usuarios, usuarios_conectados


urlpatterns = [path("health/", health_check, name="core-health")]
urlpatterns += [path("login-check/", login_check, name="login-check")]
urlpatterns += [path("logout/", logout_view, name="logout")]
urlpatterns += [path("sesion/", session_user, name="session-user")]
urlpatterns += [path("presencia/", presencia, name="presencia")]
urlpatterns += [path("usuarios-conectados/", usuarios_conectados, name="usuarios-conectados")]
urlpatterns += [path("usuarios/", usuarios, name="usuarios")]
urlpatterns += [path("usuarios/<int:user_id>/contrasena/", cambiar_contrasena_usuario, name="cambiar-contrasena-usuario")]
urlpatterns += [path("usuarios/<int:user_id>/", eliminar_usuario, name="eliminar-usuario")]

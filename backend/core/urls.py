from django.urls import path

from core.views import health_check, login_check


urlpatterns = [path("health/", health_check, name="core-health")]
urlpatterns += [path("login-check/", login_check, name="login-check")]

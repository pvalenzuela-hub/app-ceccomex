from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.csrf import ensure_csrf_cookie

from comercio.models import ArchivoCarga, Importacion
from consultas.models import ConsultaGuardada
from core.models import PresenciaUsuario


@api_view(["GET"])
@ensure_csrf_cookie
def health_check(request):
    return Response({"status": "ok", "service": "cec-comex-backend"})


@api_view(["POST"])
def login_check(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({"ok": False, "message": "Credenciales inválidas"}, status=400)
    login(request, user)
    return Response({"ok": True, "user": {"username": user.username, "email": user.email, "is_staff": user.is_staff, "is_superuser": user.is_superuser}})


@api_view(["POST"])
def logout_view(request):
    PresenciaUsuario.objects.filter(session_key=request.session.session_key).delete()
    logout(request)
    return Response({"ok": True})


@api_view(["GET"])
def session_user(request):
    if not request.user.is_authenticated:
        return Response({"detail": "Sesión no iniciada."}, status=401)
    user = request.user
    return Response({"username": user.username, "email": user.email, "is_staff": user.is_staff, "is_superuser": user.is_superuser})


def _registrar_presencia(request):
    if not request.session.session_key:
        request.session.save()
    PresenciaUsuario.objects.update_or_create(session_key=request.session.session_key, defaults={"user": request.user})


@api_view(["POST"])
def presencia(request):
    if not request.user.is_authenticated:
        return Response({"detail": "Sesión no iniciada."}, status=401)
    _registrar_presencia(request)
    return Response({"ok": True})


@api_view(["GET"])
def usuarios_conectados(request):
    if not _superuser_required(request):
        return Response({"detail": "Se requiere rol superuser."}, status=403)
    desde = timezone.now() - timedelta(minutes=2)
    return Response({"conectados": PresenciaUsuario.objects.filter(last_seen__gte=desde).values("user_id").distinct().count()})


def _superuser_required(request):
    return request.user.is_authenticated and request.user.is_superuser


@api_view(["GET", "POST"])
def usuarios(request):
    if not _superuser_required(request):
        return Response({"detail": "Se requiere rol superuser."}, status=403)
    user_model = get_user_model()
    if request.method == "GET":
        return Response(list(user_model.objects.order_by("username").values("id", "username", "first_name", "last_name", "email", "is_active", "is_staff", "is_superuser")))

    username = str(request.data.get("username", "")).strip()
    password = str(request.data.get("password", ""))
    if not username or not password:
        return Response({"detail": "Usuario y contraseña son obligatorios."}, status=400)
    if user_model.objects.filter(username=username).exists():
        return Response({"detail": "El nombre de usuario ya existe."}, status=400)
    user = user_model.objects.create_user(
        username=username,
        password=password,
        email=str(request.data.get("email", "")).strip(),
        first_name=str(request.data.get("first_name", "")).strip(),
        last_name=str(request.data.get("last_name", "")).strip(),
        is_staff=bool(request.data.get("is_staff", False)),
    )
    return Response({"id": user.id, "username": user.username}, status=201)


@api_view(["POST"])
def cambiar_contrasena_usuario(request, user_id: int):
    if not _superuser_required(request):
        return Response({"detail": "Se requiere rol superuser."}, status=403)
    password = str(request.data.get("password", ""))
    if len(password) < 8:
        return Response({"detail": "La contraseña debe tener al menos 8 caracteres."}, status=400)
    user = get_user_model().objects.filter(id=user_id).first()
    if not user:
        return Response({"detail": "Usuario no encontrado."}, status=404)
    user.set_password(password)
    user.save(update_fields=["password"])
    return Response({"ok": True})


@api_view(["DELETE"])
def eliminar_usuario(request, user_id: int):
    if not _superuser_required(request):
        return Response({"detail": "Se requiere rol superuser."}, status=403)
    if request.user.id == user_id:
        return Response({"detail": "No puede eliminar su propia cuenta."}, status=400)
    user = get_user_model().objects.filter(id=user_id).first()
    if not user:
        return Response({"detail": "Usuario no encontrado."}, status=404)
    username = user.username
    user.delete()
    return Response({"ok": True, "username": username})


@api_view(["GET"])
def system_metrics(request):
    return Response(
        {
            "cargas_totales": ArchivoCarga.objects.count(),
            "cargas_procesadas": ArchivoCarga.objects.filter(estado="PROCESADO").count(),
            "cargas_procesando": ArchivoCarga.objects.filter(estado="PROCESANDO").count(),
            "importaciones_totales": Importacion.objects.count(),
            "consultas_guardadas": ConsultaGuardada.objects.count(),
        }
    )

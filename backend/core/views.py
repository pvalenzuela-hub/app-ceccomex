import io
import json

from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.http import FileResponse
from django.utils.dateparse import parse_date
from openpyxl import Workbook
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.csrf import ensure_csrf_cookie

from comercio.models import ArchivoCarga, Importacion
from consultas.models import ConsultaGuardada
from core.actividad import ACCIONES, registrar
from core.models import PresenciaUsuario, RegistroActividad


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def health_check(request):
    return Response({"status": "ok", "service": "cec-comex-backend"})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_check(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)
    if not user:
        registrar(request, "login_fallido", "acceso", usuario_nombre=str(username))
        return Response({"ok": False, "message": "Credenciales inválidas"}, status=400)
    login(request, user)
    registrar(request, "login", "acceso")
    return Response({"ok": True, "user": {"username": user.username, "email": user.email, "is_staff": user.is_staff, "is_superuser": user.is_superuser}})


@api_view(["POST"])
def logout_view(request):
    PresenciaUsuario.objects.filter(session_key=request.session.session_key).delete()
    if request.user.is_authenticated:
        registrar(request, "logout", "acceso")
    logout(request)
    return Response({"ok": True})


@api_view(["GET"])
def session_user(request):
    user = request.user
    return Response({"username": user.username, "email": user.email, "is_staff": user.is_staff, "is_superuser": user.is_superuser})


def _registrar_presencia(request):
    if not request.session.session_key:
        request.session.save()
    PresenciaUsuario.objects.update_or_create(session_key=request.session.session_key, defaults={"user": request.user})


@api_view(["POST"])
def presencia(request):
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
    registrar(request, "usuario_creado", "usuarios", objetivo=user.username)
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
    registrar(request, "usuario_contrasena", "usuarios", objetivo=user.username)
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
    registrar(request, "usuario_eliminado", "usuarios", objetivo=username)
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


ACTIVIDAD_POR_PAGINA = 50
ACTIVIDAD_MAX_EXCEL = 50_000


def _actividad_filtrada(request, con_accion=True):
    params = request.query_params
    qs = RegistroActividad.objects.all()
    if params.get("usuario"):
        qs = qs.filter(usuario_nombre=params["usuario"])
    if con_accion and params.get("accion"):
        qs = qs.filter(accion=params["accion"])
    if params.get("modulo"):
        qs = qs.filter(modulo=params["modulo"])
    for campo, lookup in (("desde", "fecha__date__gte"), ("hasta", "fecha__date__lte")):
        fecha = parse_date(params.get(campo, "") or "")
        if fecha:
            qs = qs.filter(**{lookup: fecha})
    return qs


def _actividad_json(fila):
    return {
        "id": fila.id, "fecha": fila.fecha, "usuario": fila.usuario_nombre, "accion": fila.accion,
        "accion_texto": ACCIONES.get(fila.accion, fila.accion), "modulo": fila.modulo, "detalle": fila.detalle, "ip": fila.ip,
    }


@api_view(["GET"])
def actividad(request):
    if not _superuser_required(request):
        return Response({"detail": "Se requiere rol superuser."}, status=403)
    qs = _actividad_filtrada(request)
    page = Paginator(qs, ACTIVIDAD_POR_PAGINA).get_page(request.query_params.get("pagina", 1))
    # The summary ignores the action filter, so it always shows every kind of use of the chosen users and dates.
    resumen = _actividad_filtrada(request, con_accion=False).order_by().values("usuario_nombre").annotate(
        ingresos=Count("id", filter=Q(accion="login")),
        fallidos=Count("id", filter=Q(accion="login_fallido")),
        consultas=Count("id", filter=Q(accion="consulta")),
        excel=Count("id", filter=Q(accion="excel_descargado")),
        cargas=Count("id", filter=Q(accion="carga_archivo")),
        ultima=Max("fecha"),
    ).order_by("-ultima")
    return Response({
        "count": page.paginator.count, "pagina": page.number, "paginas": page.paginator.num_pages,
        "results": [_actividad_json(fila) for fila in page.object_list],
        "resumen": list(resumen),
        "acciones": ACCIONES,
        "usuarios": list(RegistroActividad.objects.exclude(usuario_nombre="").order_by("usuario_nombre").values_list("usuario_nombre", flat=True).distinct()),
    })


@api_view(["GET"])
def actividad_excel(request):
    if not _superuser_required(request):
        return Response({"detail": "Se requiere rol superuser."}, status=403)
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Actividad")
    sheet.append(["Fecha", "Usuario", "Acción", "Módulo", "Detalle", "IP"])
    zona = timezone.get_current_timezone()
    for fila in _actividad_filtrada(request)[:ACTIVIDAD_MAX_EXCEL]:
        sheet.append([
            fila.fecha.astimezone(zona).replace(tzinfo=None), fila.usuario_nombre, ACCIONES.get(fila.accion, fila.accion),
            fila.modulo, json.dumps(fila.detalle, ensure_ascii=False), fila.ip or "",
        ])
    archivo = io.BytesIO()
    workbook.save(archivo)
    archivo.seek(0)
    return FileResponse(archivo, as_attachment=True, filename="actividad.xlsx", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

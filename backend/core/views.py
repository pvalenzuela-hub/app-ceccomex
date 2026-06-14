from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import authenticate

from comercio.models import ArchivoCarga, Importacion
from consultas.models import ConsultaGuardada


@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok", "service": "cec-comex-backend"})


@api_view(["POST"])
def login_check(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({"ok": False, "message": "Credenciales inválidas"}, status=400)
    return Response({"ok": True, "user": {"username": user.username, "email": user.email, "is_staff": user.is_staff}})


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

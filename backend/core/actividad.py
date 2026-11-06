"""Activity log: who did what and when, recorded from the meaningful actions only."""

import ipaddress
import logging
from datetime import timedelta

from django.utils import timezone

from core.models import RegistroActividad

logger = logging.getLogger(__name__)

RETENCION_DIAS = 365

ACCIONES = {
    "login": "Inicio de sesión",
    "login_fallido": "Inicio de sesión fallido",
    "logout": "Cierre de sesión",
    "consulta": "Consulta",
    "excel_solicitado": "Excel solicitado",
    "excel_descargado": "Excel descargado",
    "carga_archivo": "Carga de archivo",
    "rubro_creado": "Rubro creado",
    "rubro_modificado": "Rubro modificado",
    "rubro_eliminado": "Rubro eliminado",
    "catalogo_creado": "Catálogo: registro creado",
    "catalogo_modificado": "Catálogo: registro modificado",
    "catalogo_eliminado": "Catálogo: registro eliminado",
    "usuario_creado": "Usuario creado",
    "usuario_contrasena": "Contraseña cambiada",
    "usuario_eliminado": "Usuario eliminado",
}


def _ip(request):
    # nginx must send X-Real-IP; without it REMOTE_ADDR is the address of the proxy, not of the user.
    value = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR") or ""
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def modulo_de(request):
    return "exportaciones" if "/exportaciones/" in request.path else "importaciones"


def registrar(request, accion, modulo="", usuario_nombre="", **detalle):
    """Store one action; a logging failure never breaks the action itself."""
    try:
        usuario = request.user if request.user.is_authenticated else None
        if accion == "login":
            RegistroActividad.objects.filter(fecha__lt=timezone.now() - timedelta(days=RETENCION_DIAS)).delete()
        RegistroActividad.objects.create(
            usuario=usuario, usuario_nombre=(usuario_nombre or (usuario.username if usuario else ""))[:150],
            accion=accion, modulo=modulo, detalle=detalle, ip=_ip(request),
        )
    except Exception:
        logger.exception("No se pudo registrar la actividad %s", accion)

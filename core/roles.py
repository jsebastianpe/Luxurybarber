"""Roles del panel: admin, recepcion, barbero.

- admin: superusuario o miembro del grupo "Admin"
- recepcion: miembro del grupo "Recepcion"
- barbero: usuario enlazado a un Barbero
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

ADMIN, RECEPCION, BARBERO = "admin", "recepcion", "barbero"


def rol_de(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser or user.groups.filter(name="Admin").exists():
        return ADMIN
    if user.groups.filter(name="Recepcion").exists():
        return RECEPCION
    if hasattr(user, "barbero") and user.barbero is not None:
        return BARBERO
    return None


def requiere_rol(*roles):
    def deco(view):
        @login_required
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            rol = rol_de(request.user)
            if rol is None or (roles and rol not in roles):
                raise PermissionDenied("No tienes acceso a este módulo")
            request.rol = rol
            return view(request, *args, **kwargs)
        return _wrapped
    return deco

from django.conf import settings

from .roles import rol_de


def negocio(request):
    ctx = {"NEGOCIO": settings.BARBERIA, "NEGOCIO_TAILWIND_CDN": settings.TAILWIND_CDN}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        ctx["ROL"] = rol_de(user)
    return ctx

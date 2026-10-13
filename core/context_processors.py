from datetime import date

from django.conf import settings

from .roles import rol_de


def negocio(request):
    ctx = {
        "NEGOCIO": settings.BARBERIA,
        "NEGOCIO_TAILWIND_CDN": settings.TAILWIND_CDN,
        "RESP": settings.RESPONSABLE,
        "RESP_NOMBRE": settings.RESPONSABLE["RAZON_SOCIAL"] or settings.BARBERIA["NOMBRE"],
        "POLITICA_VERSION": settings.POLITICA_VERSION,
        "POLITICA_VIGENCIA": date.fromisoformat(settings.POLITICA_VIGENCIA),
        "TERMINOS_VERSION": settings.TERMINOS_VERSION,
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        ctx["ROL"] = rol_de(user)
    return ctx

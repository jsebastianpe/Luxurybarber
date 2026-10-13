"""Chequeos de despliegue: impiden lanzar a producción sin los datos legales mínimos."""
from django.conf import settings
from django.core.checks import Error, Warning, register


@register(deploy=True)
def datos_responsable(app_configs, **kwargs):
    from .privacidad import faltantes_responsable
    errores = []
    faltan = faltantes_responsable()
    if faltan:
        errores.append(Error(
            "Faltan datos del responsable del tratamiento: " + ", ".join(faltan) + ".",
            hint="Complétalos en .env (RESP_RAZON_SOCIAL, RESP_NUMERO_ID, RESP_EMAIL_DATOS...). "
                 "Son obligatorios en la política (Decreto 1074 de 2015, art. 2.2.2.25.3.1) y en el sitio (Ley 1480 art. 50).",
            id="barberia.E001"))
    if settings.SECRET_KEY.startswith("dev-"):
        errores.append(Error("DJANGO_SECRET_KEY de desarrollo.", hint="Genera una clave nueva y larga.", id="barberia.E002"))
    w = settings.WHATSAPP
    if settings.MENSAJES_BACKEND == "whatsapp":
        faltan = [n for n, v in (("WHATSAPP_TOKEN", w["TOKEN"]), ("WHATSAPP_PHONE_ID", w["PHONE_ID"]),
                                 ("WHATSAPP_PLANTILLA_OTP", w["PLANTILLA_OTP"])) if not v]
        if faltan:
            errores.append(Error(f"WhatsApp activo pero faltan: {', '.join(faltan)}.", id="barberia.E003"))
        if not (w["APP_SECRET"] and w["VERIFY_TOKEN"]):
            errores.append(Warning("Sin WHATSAPP_APP_SECRET / WHATSAPP_VERIFY_TOKEN el webhook rechaza todo y no "
                                   "verás si los códigos se entregaron.", id="barberia.W003"))
        elif len(w["VERIFY_TOKEN"]) < 24:
            errores.append(Warning("WHATSAPP_VERIFY_TOKEN corto: usa al menos 32 caracteres aleatorios.", id="barberia.W004"))
        if not settings.SITIO_URL.startswith("https://"):
            errores.append(Error("SITIO_URL debe ser https:// (enlaces de los mensajes y webhook).", id="barberia.E004"))
    if not settings.OTP["PIMIENTA"]:
        errores.append(Warning("OTP_PIMIENTA vacía: la huella de los códigos se deriva de SECRET_KEY. "
                               "Define una clave propia para separar secretos.", id="barberia.W005"))
    if settings.MENSAJES_BACKEND == "consola":
        errores.append(Warning("Los mensajes se imprimen en consola; los clientes no recibirán confirmaciones.",
                               id="barberia.W001"))
    if settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
        errores.append(Warning("SQLite en producción: usa PostgreSQL con copias de seguridad cifradas.",
                               id="barberia.W002"))
    return errores

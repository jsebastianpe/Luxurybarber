"""Envío de mensajes (WhatsApp / consola) y textos de plantillas.

MENSAJES_BACKEND=consola  -> imprime en la terminal y guarda en MensajeEnviado (desarrollo)
MENSAJES_BACKEND=whatsapp -> WhatsApp Cloud API de Meta (requiere WHATSAPP_TOKEN y WHATSAPP_PHONE_ID).

Nota: para escribir a un cliente fuera de la ventana de 24 h, Meta exige plantillas
aprobadas. Aquí se envía texto libre por simplicidad; en producción cambia
`_enviar_whatsapp` para usar `type: "template"` con tus plantillas aprobadas.
"""
import json
import logging
import urllib.request

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import MensajeEnviado
from .templatetags.barberia import cop, fecha_larga, hora

log = logging.getLogger("core")


def _url(nombre, *args):
    return settings.SITIO_URL.rstrip("/") + reverse(nombre, args=args)


def _enviar_whatsapp(telefono, texto):
    url = f"https://graph.facebook.com/v20.0/{settings.WHATSAPP_PHONE_ID}/messages"
    data = json.dumps({
        "messaging_product": "whatsapp",
        "to": telefono.lstrip("+"),
        "type": "text",
        "text": {"body": texto},
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        return 200 <= r.status < 300


def enviar(telefono, texto, tipo, cliente=None, cita=None):
    canal = settings.MENSAJES_BACKEND
    ok = True
    if canal == "whatsapp":
        try:
            ok = _enviar_whatsapp(telefono, texto)
        except Exception as exc:  # noqa: BLE001
            log.exception("Fallo enviando WhatsApp: %s", exc)
            ok = False
    else:
        log.info("\n📱 [%s] para %s\n%s\n", tipo, telefono, texto)
    return MensajeEnviado.objects.create(
        telefono=telefono, cliente=cliente, cita=cita, tipo=tipo, canal=canal, contenido=texto, ok=ok
    )


def _detalle(cita):
    ini = timezone.localtime(cita.inicio)
    return (
        f"{cita.nombres_servicios} con {cita.barbero.nombre}\n"
        f"{fecha_larga(ini)} a las {hora(ini)}\n"
        f"{settings.BARBERIA['NOMBRE']} · {settings.BARBERIA['DIRECCION']}"
    )


def enviar_otp(telefono, codigo):
    texto = f"Tu código de {settings.BARBERIA['NOMBRE']} es {codigo}. Vence en 10 minutos."
    return enviar(telefono, texto, "otp")


def confirmacion(cita):
    c = cita.cliente
    texto = (
        f"¡Listo, {c.primer_nombre}! Tu cita quedó reservada ✂️\n{_detalle(cita)}\n"
        f"Total: {cop(cita.precio_total)}\n"
        f"Gestiona tu cita: {_url('cliente:un_toque', cita.token)}"
    )
    return enviar(c.telefono, texto, "confirmacion", c, cita)


def recordatorio(cita, tipo):
    c = cita.cliente
    cuando = "mañana" if tipo == "recordatorio_24h" else "en 2 horas"
    texto = (
        f"Hola {c.primer_nombre}, te esperamos {cuando}.\n{_detalle(cita)}\n"
        f"Confirma, reprograma o cancela con un toque: {_url('cliente:un_toque', cita.token)}"
    )
    return enviar(c.telefono, texto, tipo, c, cita)


def cancelacion(cita):
    c = cita.cliente
    texto = f"{c.primer_nombre}, cancelamos tu cita del {fecha_larga(timezone.localtime(cita.inicio))}. Reserva cuando quieras: {_url('cliente:inicio')}"
    return enviar(c.telefono, texto, "cancelacion", c, cita)


def reactivacion(cliente, mensaje=None):
    texto = mensaje or (
        f"¡{cliente.primer_nombre}, te extrañamos! Hace {cliente.dias_inactivo} días no te vemos. "
        f"Tienes {cliente.puntos} puntos esperando. Reserva aquí: {_url('cliente:inicio')}"
    )
    texto = texto.replace("{nombre}", cliente.primer_nombre).replace("{puntos}", str(cliente.puntos)).replace(
        "{dias}", str(cliente.dias_inactivo or "")
    ).replace("{enlace}", _url("cliente:inicio"))
    return enviar(cliente.telefono, texto, "reactivacion", cliente)

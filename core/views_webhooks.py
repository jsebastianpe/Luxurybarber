"""Webhook de WhatsApp Cloud API: actualiza el estado de entrega de códigos y mensajes.

Seguridad:
- GET: verificación del endpoint con el verify token (comparación en tiempo constante).
- POST: se rechaza todo lo que no traiga una firma X-Hub-Signature-256 válida, calculada con el app secret
  sobre el cuerpo crudo. Sin firma válida no se lee ni se procesa nada.
- Cuerpo máximo de 1 MB y procesamiento idempotente: Meta reintenta hasta 7 días.
- No guarda el contenido de los mensajes entrantes. Solo se usan los estados de entrega.
"""
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import whatsapp as wa
from .models import ORDEN_ESTADOS, CodigoVerificacion, MensajeEnviado

log = logging.getLogger("core.whatsapp")
MAX_BYTES = 1024 * 1024
ESTADOS = {"sent": "enviado", "delivered": "entregado", "read": "leido", "failed": "fallido"}


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp(request):
    if request.method == "GET":
        token = settings.WHATSAPP["VERIFY_TOKEN"]
        recibido = request.GET.get("hub.verify_token", "")
        if (token and request.GET.get("hub.mode") == "subscribe"
                and hmac.compare_digest(token.encode(), recibido.encode())):
            return HttpResponse(request.GET.get("hub.challenge", ""), content_type="text/plain")
        return HttpResponseForbidden()

    if int(request.META.get("CONTENT_LENGTH") or 0) > MAX_BYTES:
        return HttpResponseBadRequest()
    cuerpo = request.body
    if not wa.firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256")):
        log.warning("Webhook WhatsApp con firma inválida desde %s", request.META.get("REMOTE_ADDR"))
        return HttpResponseForbidden()
    try:
        datos = json.loads(cuerpo)
    except ValueError:
        return HttpResponseBadRequest()

    for wamid, estado_meta, codigo_err, titulo in wa.estados_del_webhook(datos):
        estado = ESTADOS.get(estado_meta)
        if not (wamid and estado):
            continue
        error = f"{codigo_err} {titulo}".strip()[:160] if estado == "fallido" else ""
        for modelo in (CodigoVerificacion, MensajeEnviado):
            for obj in modelo.objects.filter(wamid=wamid):
                # Los estados llegan desordenados: solo se avanza (enviado → entregado → leído), o a fallido.
                if ORDEN_ESTADOS.get(estado, 0) > ORDEN_ESTADOS.get(obj.estado, 0) or estado == "fallido":
                    obj.estado = estado
                    campos = ["estado"]
                    if error:
                        obj.error = error
                        campos.append("error")
                    if modelo is MensajeEnviado:
                        obj.ok = estado != "fallido"
                        campos.append("ok")
                    obj.save(update_fields=campos)
    return HttpResponse("ok")

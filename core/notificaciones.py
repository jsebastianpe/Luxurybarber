<<<<<<< HEAD
"""Envío de mensajes al cliente.

MENSAJES_BACKEND=consola  -> imprime en la terminal y guarda en MensajeEnviado (desarrollo)
MENSAJES_BACKEND=whatsapp -> WhatsApp Cloud API de Meta (core/whatsapp.py)

Fuera de la ventana de 24 h, Meta solo entrega mensajes iniciados por la empresa si usan plantillas
aprobadas. Por eso cada tipo de mensaje tiene su plantilla (WHATSAPP_PLANTILLA_*). Si una plantilla no está
configurada se envía texto libre, que solo llega si el cliente escribió en las últimas 24 h.
"""
import logging
from dataclasses import dataclass
=======
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
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

<<<<<<< HEAD
from . import whatsapp as wa
=======
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
from .models import MensajeEnviado
from .templatetags.barberia import cop, fecha_larga, hora

log = logging.getLogger("core")


def _url(nombre, *args):
    return settings.SITIO_URL.rstrip("/") + reverse(nombre, args=args)


<<<<<<< HEAD
def _plantilla(clave):
    return settings.WHATSAPP.get(f"PLANTILLA_{clave}") or ""


def enviar(telefono, texto, tipo, cliente=None, cita=None, plantilla="", parametros=()):
    """Envía y registra el mensaje. Nunca lanza excepción: un fallo de WhatsApp no debe tumbar la reserva."""
    canal = settings.MENSAJES_BACKEND
    wamid, estado, error = "", "enviado", ""
    if canal == "whatsapp":
        try:
            if plantilla:
                res = wa.enviar_plantilla(telefono, plantilla, wa.parametros_cuerpo(*parametros))
            else:
                res = wa.enviar_texto(telefono, texto)
            wamid = res.wamid
        except wa.WhatsAppError as e:
            estado, error = "fallido", f"{e.codigo or ''} {e}"[:160]
            (log.error if e.es_configuracion else log.warning)(
                "WhatsApp no enviado (%s) a %s: %s", tipo, wa.enmascarar(telefono), e)
    else:
        log.info("\n📱 [%s] para %s\n%s\n", tipo, telefono, texto)
    return MensajeEnviado.objects.create(
        telefono=telefono, cliente=cliente, cita=cita, tipo=tipo, canal=canal, contenido=texto,
        ok=estado != "fallido", wamid=wamid, estado=estado, error=error,
    )


@dataclass
class EnvioOTP:
    wamid: str = ""
    estado: str = "enviado"
    error: str = ""
    error_usuario: str = ""


def enviar_otp(telefono, codigo) -> EnvioOTP:
    """El código no se guarda en el historial de mensajes ni se escribe en logs de producción."""
    canal = settings.MENSAJES_BACKEND
    envio = EnvioOTP()
    if canal == "whatsapp":
        try:
            envio.wamid = wa.enviar_otp(telefono, codigo).wamid
        except wa.WhatsAppError as e:
            envio.estado, envio.error, envio.error_usuario = "fallido", f"{e.codigo or ''} {e}"[:160], e.para_usuario
            (log.error if e.es_configuracion else log.warning)(
                "OTP no enviado a %s: %s", wa.enmascarar(telefono), e)
    elif settings.DEBUG:
        log.info("\n📱 [otp] para %s\nTu código de verificación es %s\n", telefono, codigo)
    MensajeEnviado.objects.create(
        telefono=telefono, tipo="otp", canal=canal, contenido="[código de verificación — no se almacena]",
        ok=envio.estado != "fallido", wamid=envio.wamid, estado=envio.estado, error=envio.error,
    )
    return envio


=======
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


>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
def _detalle(cita):
    ini = timezone.localtime(cita.inicio)
    return (
        f"{cita.nombres_servicios} con {cita.barbero.nombre}\n"
        f"{fecha_larga(ini)} a las {hora(ini)}\n"
        f"{settings.BARBERIA['NOMBRE']} · {settings.BARBERIA['DIRECCION']}"
    )


<<<<<<< HEAD
def _cuando(cita):
    ini = timezone.localtime(cita.inicio)
    return f"{fecha_larga(ini)} a las {hora(ini)}"
=======
def enviar_otp(telefono, codigo):
    texto = f"Tu código de {settings.BARBERIA['NOMBRE']} es {codigo}. Vence en 10 minutos."
    return enviar(telefono, texto, "otp")
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad


def confirmacion(cita):
    c = cita.cliente
<<<<<<< HEAD
    if not c.acepta_whatsapp:
        return None
    enlace = _url("cliente:un_toque", cita.token)
    texto = (
        f"¡Listo, {c.primer_nombre}! Tu cita quedó reservada ✂️\n{_detalle(cita)}\n"
        f"Total: {cop(cita.precio_total)}\nGestiona tu cita: {enlace}"
    )
    # Plantilla sugerida (utilidad): {{1}} nombre, {{2}} servicios, {{3}} barbero, {{4}} fecha y hora, {{5}} total, {{6}} enlace
    return enviar(c.telefono, texto, "confirmacion", c, cita, _plantilla("CONFIRMACION"),
                  (c.primer_nombre, cita.nombres_servicios, cita.barbero.nombre, _cuando(cita),
                   cop(cita.precio_total), enlace))
=======
    texto = (
        f"¡Listo, {c.primer_nombre}! Tu cita quedó reservada ✂️\n{_detalle(cita)}\n"
        f"Total: {cop(cita.precio_total)}\n"
        f"Gestiona tu cita: {_url('cliente:un_toque', cita.token)}"
    )
    return enviar(c.telefono, texto, "confirmacion", c, cita)
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad


def recordatorio(cita, tipo):
    c = cita.cliente
    cuando = "mañana" if tipo == "recordatorio_24h" else "en 2 horas"
<<<<<<< HEAD
    enlace = _url("cliente:un_toque", cita.token)
    texto = (
        f"Hola {c.primer_nombre}, te esperamos {cuando}.\n{_detalle(cita)}\n"
        f"Confirma, reprograma o cancela con un toque: {enlace}"
    )
    # Plantilla (utilidad): {{1}} nombre, {{2}} cuándo, {{3}} servicios, {{4}} fecha y hora, {{5}} enlace
    return enviar(c.telefono, texto, tipo, c, cita, _plantilla("RECORDATORIO"),
                  (c.primer_nombre, cuando, cita.nombres_servicios, _cuando(cita), enlace))
=======
    texto = (
        f"Hola {c.primer_nombre}, te esperamos {cuando}.\n{_detalle(cita)}\n"
        f"Confirma, reprograma o cancela con un toque: {_url('cliente:un_toque', cita.token)}"
    )
    return enviar(c.telefono, texto, tipo, c, cita)
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad


def cancelacion(cita):
    c = cita.cliente
<<<<<<< HEAD
    if not c.acepta_whatsapp or c.anonimizado_en:
        return None
    enlace = _url("cliente:inicio")
    texto = f"{c.primer_nombre}, cancelamos tu cita del {fecha_larga(timezone.localtime(cita.inicio))}. Reserva cuando quieras: {enlace}"
    # Plantilla (utilidad): {{1}} nombre, {{2}} fecha y hora, {{3}} enlace
    return enviar(c.telefono, texto, "cancelacion", c, cita, _plantilla("CANCELACION"),
                  (c.primer_nombre, _cuando(cita), enlace))


def reactivacion(cliente, mensaje=None):
    """Mensaje publicitario. Llamar solo después de privacidad.puede_recibir_publicidad() (Ley 2300 de 2023).

    Con plantilla de marketing configurada se usa la plantilla aprobada (el texto del panel se ignora,
    porque Meta no permite texto libre fuera de la ventana de 24 h).
    """
    texto = mensaje or (
        "¡{nombre}, te extrañamos! Hace {dias} días no te vemos. Tienes {puntos} puntos esperando. Reserva aquí: {enlace}"
=======
    texto = f"{c.primer_nombre}, cancelamos tu cita del {fecha_larga(timezone.localtime(cita.inicio))}. Reserva cuando quieras: {_url('cliente:inicio')}"
    return enviar(c.telefono, texto, "cancelacion", c, cita)


def reactivacion(cliente, mensaje=None):
    texto = mensaje or (
        f"¡{cliente.primer_nombre}, te extrañamos! Hace {cliente.dias_inactivo} días no te vemos. "
        f"Tienes {cliente.puntos} puntos esperando. Reserva aquí: {_url('cliente:inicio')}"
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
    )
    texto = texto.replace("{nombre}", cliente.primer_nombre).replace("{puntos}", str(cliente.puntos)).replace(
        "{dias}", str(cliente.dias_inactivo or "")
    ).replace("{enlace}", _url("cliente:inicio"))
<<<<<<< HEAD
    baja = _url("legal:baja", cliente.token_baja)
    texto += (f"\n\nMensaje publicitario de {settings.RESPONSABLE['RAZON_SOCIAL'] or settings.BARBERIA['NOMBRE']}. "
              f"Para no recibir más promociones: {baja}")
    # Plantilla (marketing): {{1}} nombre, {{2}} días, {{3}} puntos, {{4}} enlace para reservar, {{5}} enlace de baja
    return enviar(cliente.telefono, texto, "reactivacion", cliente, None, _plantilla("PROMOCION"),
                  (cliente.primer_nombre, cliente.dias_inactivo or "", cliente.puntos, _url("cliente:inicio"), baja))
=======
    return enviar(cliente.telefono, texto, "reactivacion", cliente)
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad

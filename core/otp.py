"""Códigos de verificación (OTP) por WhatsApp.

Medidas de seguridad:
- Código de 6 dígitos con generador criptográfico (`secrets`).
- En la base solo se guarda HMAC-SHA256(pimienta, teléfono:código). Si alguien roba la base, no puede leer
  los códigos; la pimienta vive fuera de la base (variable de entorno o SECRET_KEY).
- Comparación en tiempo constante (`hmac.compare_digest`).
- Vigencia corta (10 min), 3 intentos por código, un solo uso; cada código nuevo anula los anteriores.
- Límites por celular, por IP y un tope diario global para frenar el abuso que genera costos en Meta.
- Solo se envía a los países permitidos (WHATSAPP_PAISES_OTP), para prevenir fraude por bombeo de mensajes.
- El código nunca se registra en logs ni en el historial de mensajes; en desarrollo se muestra solo con
  DEBUG=1 y el canal de consola.
"""
import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from . import notificaciones
from .models import CodigoVerificacion


def normalizar_telefono(valor: str) -> str | None:
    """'300 123 4567' -> '+573001234567'. Devuelve None si no parece un celular válido."""
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) == 10 and digitos.startswith("3"):
        return "+57" + digitos
    if len(digitos) == 12 and digitos.startswith("573"):
        return "+" + digitos
    if valor and valor.strip().startswith("+") and 8 <= len(digitos) <= 15 and not digitos.startswith("57"):
        return "+" + digitos
    return None


def pais_permitido(telefono: str) -> bool:
    digitos = telefono.lstrip("+")
    return any(digitos.startswith(p) for p in settings.WHATSAPP["PAISES_OTP"])


def _pimienta() -> bytes:
    p = settings.OTP["PIMIENTA"]
    if p:
        return p.encode()
    return hashlib.sha256(b"otp-pimienta:" + settings.SECRET_KEY.encode()).digest()


def huella(telefono: str, codigo: str) -> str:
    return hmac.new(_pimienta(), f"{telefono}:{codigo}".encode(), hashlib.sha256).hexdigest()


def _generar_codigo() -> str:
    n = settings.OTP["LONGITUD"]
    return f"{secrets.randbelow(10 ** n):0{n}d}"


def enviar_codigo(telefono, ip=None):
    """Crea y envía un código. Devuelve (registro | None, error_para_usuario | None, codigo_debug | None)."""
    from .privacidad import limite_excedido
    lim, cfg = settings.LIMITES, settings.OTP

    if not pais_permitido(telefono):
        return None, "Por ahora solo enviamos códigos a celulares de Colombia.", None
    if limite_excedido(f"otp-tel:{telefono}", lim["OTP_POR_TELEFONO_HORA"], 3600) or (
            ip and limite_excedido(f"otp-ip:{ip}", lim["OTP_POR_IP_HORA"], 3600)):
        return None, "Pediste demasiados códigos. Intenta de nuevo en una hora.", None
    if limite_excedido(f"otp-global:{timezone.localdate():%Y%m%d}", cfg["TOPE_DIARIO_GLOBAL"], 86400):
        return None, "No podemos enviar códigos en este momento. Escríbenos por WhatsApp para reservar.", None

    ultimo = CodigoVerificacion.objects.filter(telefono=telefono, usado=False, invalidado=False).order_by("-creado").first()
    if ultimo and (timezone.now() - ultimo.creado).total_seconds() < cfg["REENVIO_SEG"] and ultimo.estado != "fallido":
        return ultimo, f"Espera {cfg['REENVIO_SEG']} segundos para pedir otro código.", None

    CodigoVerificacion.objects.filter(telefono=telefono, usado=False, invalidado=False).update(invalidado=True)
    codigo = _generar_codigo()
    reg = CodigoVerificacion.objects.create(
        telefono=telefono, codigo_hash=huella(telefono, codigo), ip=ip,
        expira=timezone.now() + timedelta(minutes=cfg["VIGENCIA_MIN"]),
    )
    envio = notificaciones.enviar_otp(telefono, codigo)
    reg.wamid, reg.estado, reg.error = envio.wamid, envio.estado, envio.error
    reg.save(update_fields=["wamid", "estado", "error"])
    error = envio.error_usuario if envio.estado == "fallido" else None
    debug = codigo if (settings.DEBUG and settings.MENSAJES_BACKEND == "consola") else None
    return reg, error, debug


def verificar(telefono, codigo) -> str | None:
    """Devuelve None si el código es válido, o el mensaje de error."""
    codigo = re.sub(r"\D", "", codigo or "")
    reg = (CodigoVerificacion.objects.filter(telefono=telefono, usado=False, invalidado=False)
           .order_by("-creado").first())
    if reg is None or reg.expira < timezone.now():
        return "El código venció. Pide uno nuevo."
    if reg.intentos >= settings.OTP["INTENTOS"]:
        return "Demasiados intentos. Pide un código nuevo."
    if not (codigo and hmac.compare_digest(reg.codigo_hash, huella(telefono, codigo))):
        reg.intentos += 1
        reg.save(update_fields=["intentos"])
        restantes = settings.OTP["INTENTOS"] - reg.intentos
        return f"Código incorrecto. Te quedan {restantes} intento(s)." if restantes else "Demasiados intentos. Pide un código nuevo."
    reg.usado = True
    reg.save(update_fields=["usado"])
    return None

import random
import re
from datetime import timedelta

from django.utils import timezone

from . import notificaciones
from .models import CodigoVerificacion

MAX_INTENTOS = 3
REENVIO_SEG = 30


def normalizar_telefono(valor: str) -> str | None:
    """'300 123 4567' -> '+573001234567'. Devuelve None si no parece un celular válido."""
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) == 10 and digitos.startswith("3"):
        return "+57" + digitos
    if len(digitos) == 12 and digitos.startswith("57"):
        return "+" + digitos
    if valor and valor.strip().startswith("+") and 8 <= len(digitos) <= 15:
        return "+" + digitos
    return None


def enviar_codigo(telefono):
    """Crea y envía un código. Devuelve (registro, error)."""
    ultimo = CodigoVerificacion.objects.filter(telefono=telefono).order_by("-creado").first()
    if ultimo and (timezone.now() - ultimo.creado).total_seconds() < REENVIO_SEG and not ultimo.usado:
        return ultimo, f"Espera {REENVIO_SEG} segundos para pedir otro código."
    codigo = f"{random.SystemRandom().randint(0, 999999):06d}"
    reg = CodigoVerificacion.objects.create(
        telefono=telefono, codigo=codigo, expira=timezone.now() + timedelta(minutes=10)
    )
    notificaciones.enviar_otp(telefono, codigo)
    return reg, None


def verificar(telefono, codigo) -> str | None:
    """Devuelve None si el código es válido, o el mensaje de error."""
    reg = CodigoVerificacion.objects.filter(telefono=telefono, usado=False).order_by("-creado").first()
    if reg is None or reg.expira < timezone.now():
        return "El código venció. Pide uno nuevo."
    if reg.intentos >= MAX_INTENTOS:
        return "Demasiados intentos. Pide un código nuevo."
    if reg.codigo != (codigo or "").strip():
        reg.intentos += 1
        reg.save(update_fields=["intentos"])
        restantes = MAX_INTENTOS - reg.intentos
        return f"Código incorrecto. Te quedan {restantes} intento(s)." if restantes else "Demasiados intentos. Pide un código nuevo."
    reg.usado = True
    reg.save(update_fields=["usado"])
    return None

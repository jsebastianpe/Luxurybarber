"""Filtros de formato para Colombia: pesos sin decimales, hora 12 h, fechas en español."""
from datetime import date, datetime

from django import template
from django.utils import timezone

register = template.Library()

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DIAS_CORTOS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _local(v):
    if isinstance(v, datetime) and timezone.is_aware(v):
        return timezone.localtime(v)
    return v


@register.filter
def cop(valor):
    """35000 -> $35.000"""
    try:
        n = int(round(float(valor or 0)))
    except (TypeError, ValueError):
        return valor
    signo = "-" if n < 0 else ""
    return f"{signo}${abs(n):,}".replace(",", ".")


@register.filter
def hora(v):
    """datetime/time -> 3:30 p. m."""
    v = _local(v)
    if v in (None, ""):
        return ""
    h, m = v.hour, v.minute
    sufijo = "a. m." if h < 12 else "p. m."
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {sufijo}"


@register.filter
def hora_corta(v):
    """3:30 (sin sufijo)"""
    v = _local(v)
    h12 = v.hour % 12 or 12
    return f"{h12}:{v.minute:02d}"


@register.filter
def fecha_larga(v):
    """sábado 10 de octubre"""
    v = _local(v)
    if isinstance(v, datetime):
        v = v.date()
    if not isinstance(v, date):
        return v
    return f"{DIAS[v.weekday()]} {v.day} de {MESES[v.month - 1]}"


@register.filter
def dia_corto(v):
    v = _local(v)
    return DIAS_CORTOS[v.weekday()]


@register.filter
def mes(v):
    return MESES[_local(v).month - 1]


@register.filter
def iso(v):
    v = _local(v)
    return v.isoformat()


@register.filter
def minutos(n):
    n = int(n or 0)
    if n < 60:
        return f"{n} min"
    h, m = divmod(n, 60)
    return f"{h} h {m} min" if m else f"{h} h"


@register.filter
def get(d, k):
    try:
        return d.get(k)
    except AttributeError:
        return None


@register.filter(name="abs")
def valor_absoluto(n):
    try:
        return abs(int(n))
    except (TypeError, ValueError):
        return n

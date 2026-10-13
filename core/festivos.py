"""Festivos de Colombia (Ley 51 de 1983 "Ley Emiliani") y cálculo de días hábiles.

Se usa para los plazos de la Ley 1581 de 2012 (consultas: 10 días hábiles; reclamos: 15 días hábiles)
y para no enviar publicidad en festivos (Ley 2300 de 2023).
"""
from datetime import date, timedelta
from functools import lru_cache


def _pascua(anio: int) -> date:
    """Domingo de Pascua (algoritmo anónimo gregoriano)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def _siguiente_lunes(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7)


@lru_cache(maxsize=32)
def festivos(anio: int) -> frozenset:
    fijos = [date(anio, 1, 1), date(anio, 5, 1), date(anio, 7, 20), date(anio, 8, 7),
             date(anio, 12, 8), date(anio, 12, 25)]
    trasladables = [date(anio, 1, 6), date(anio, 3, 19), date(anio, 6, 29), date(anio, 8, 15),
                    date(anio, 10, 12), date(anio, 11, 1), date(anio, 11, 11)]
    p = _pascua(anio)
    semana_santa = [p - timedelta(days=3), p - timedelta(days=2)]  # jueves y viernes santo
    moviles = [p + timedelta(days=43), p + timedelta(days=64), p + timedelta(days=71)]  # Ascensión, Corpus, Sagrado Corazón (ya en lunes)
    return frozenset(fijos + [_siguiente_lunes(d) for d in trasladables] + semana_santa + moviles)


def es_festivo(d: date) -> bool:
    return d in festivos(d.year)


def es_habil(d: date) -> bool:
    return d.weekday() < 5 and not es_festivo(d)


def sumar_dias_habiles(desde: date, dias: int) -> date:
    """Cuenta `dias` hábiles a partir del día siguiente a `desde`."""
    d = desde
    contados = 0
    while contados < dias:
        d += timedelta(days=1)
        if es_habil(d):
            contados += 1
    return d

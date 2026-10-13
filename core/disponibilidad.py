"""Cálculo de disponibilidad y creación segura de citas.

Toda la lógica de "qué horas están libres" vive en el servidor: el frontend
solo muestra lo que devuelve este módulo.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Barbero, Bloqueo, Cita, RetencionCupo

CFG = settings.BARBERIA


class CupoNoDisponible(Exception):
    pass


@dataclass(frozen=True)
class Slot:
    inicio: datetime
    fin: datetime
    barbero_id: int


def _aware(d: date, t: time) -> datetime:
    return timezone.make_aware(datetime.combine(d, t), timezone.get_current_timezone())


def _se_cruzan(a_ini, a_fin, b_ini, b_fin):
    return a_ini < b_fin and b_ini < a_fin


def ocupaciones(barbero: Barbero, dia: date, excluir_sesion: str | None = None):
    """Intervalos ocupados del barbero en el día: citas, bloqueos y retenciones ajenas vigentes."""
    ini_dia = _aware(dia, time.min)
    fin_dia = ini_dia + timedelta(days=1)
    intervalos = list(
        Cita.objects.filter(barbero=barbero, estado__in=Cita.ACTIVAS, inicio__lt=fin_dia, fin__gt=ini_dia)
        .values_list("inicio", "fin")
    )
    intervalos += list(
        Bloqueo.objects.filter(barbero=barbero, inicio__lt=fin_dia, fin__gt=ini_dia).values_list("inicio", "fin")
    )
    ret = RetencionCupo.objects.filter(
        barbero=barbero, expira__gt=timezone.now(), inicio__lt=fin_dia, fin__gt=ini_dia
    )
    if excluir_sesion:
        ret = ret.exclude(clave_sesion=excluir_sesion)
    intervalos += list(ret.values_list("inicio", "fin"))
    return intervalos


def horarios_libres(barbero: Barbero, dia: date, duracion_min: int, excluir_sesion=None):
    """Lista de Slot libres para un barbero en un día."""
    paso = timedelta(minutes=CFG["PASO_MINUTOS"])
    duracion = timedelta(minutes=duracion_min)
    limite = timezone.now() + timedelta(minutes=CFG["ANTICIPACION_MIN"])
    ocupado = ocupaciones(barbero, dia, excluir_sesion)
    slots = []
    for h in barbero.horarios.filter(dia_semana=dia.weekday()):
        cursor = _aware(dia, h.hora_inicio)
        fin_turno = _aware(dia, h.hora_fin)
        while cursor + duracion <= fin_turno:
            fin = cursor + duracion
            if cursor >= limite and not any(_se_cruzan(cursor, fin, a, b) for a, b in ocupado):
                slots.append(Slot(cursor, fin, barbero.id))
            cursor += paso
    return slots


def barberos_para(servicio_ids):
    """Barberos activos que realizan TODOS los servicios elegidos."""
    qs = Barbero.objects.filter(activo=True)
    for sid in servicio_ids:
        qs = qs.filter(servicios__id=sid)
    return qs.distinct()


def horarios_combinados(barberos, dia, duracion_min, excluir_sesion=None):
    """Para 'Cualquier barbero': une horarios y asigna al barbero con menos carga ese día."""
    carga = {}
    por_hora = {}
    for b in barberos:
        carga[b.id] = Cita.objects.filter(
            barbero=b, estado__in=Cita.ACTIVAS, inicio__date=dia
        ).count()
        for s in horarios_libres(b, dia, duracion_min, excluir_sesion):
            actual = por_hora.get(s.inicio)
            if actual is None or carga[b.id] < carga[actual.barbero_id]:
                por_hora[s.inicio] = s
    return [por_hora[k] for k in sorted(por_hora)]


def resumen_dias(barberos, duracion_min, desde: date, dias: int, excluir_sesion=None):
    """Para la tira de días: cantidad de horas libres por día (0 = sin cupos)."""
    out = []
    for i in range(dias):
        d = desde + timedelta(days=i)
        n = len(horarios_combinados(barberos, d, duracion_min, excluir_sesion))
        nivel = "sin" if n == 0 else ("pocos" if n <= 4 else "ok")
        out.append({"fecha": d, "libres": n, "nivel": nivel})
    return out


def proximo_cupo(barbero, duracion_min, dias=14):
    hoy = timezone.localdate()
    for i in range(dias):
        slots = horarios_libres(barbero, hoy + timedelta(days=i), duracion_min)
        if slots:
            return slots[0].inicio
    return None


def retener(barbero: Barbero, inicio: datetime, duracion_min: int, clave_sesion: str) -> RetencionCupo:
    """Retiene un cupo N minutos. Lanza CupoNoDisponible si ya no está libre."""
    fin = inicio + timedelta(minutes=duracion_min)
    with transaction.atomic():
        Barbero.objects.select_for_update().get(pk=barbero.pk)  # serializa por barbero
        RetencionCupo.objects.filter(clave_sesion=clave_sesion).delete()
        RetencionCupo.objects.filter(expira__lte=timezone.now()).delete()
        libres = horarios_libres(barbero, timezone.localtime(inicio).date(), duracion_min, clave_sesion)
        if not any(s.inicio == inicio for s in libres):
            raise CupoNoDisponible
        return RetencionCupo.objects.create(
            barbero=barbero,
            inicio=inicio,
            fin=fin,
            clave_sesion=clave_sesion,
            expira=timezone.now() + timedelta(minutes=CFG["RETENCION_MIN"]),
        )


def crear_cita(*, cliente, barbero, servicios, inicio, clave_sesion=None, origen="web", notas="", estado=Cita.CONFIRMADA,
               validar_horario=True):
    """Crea la cita validando de nuevo dentro de una transacción (evita dobles reservas)."""
    duracion = sum(s.duracion_min for s in servicios)
    fin = inicio + timedelta(minutes=duracion)
    with transaction.atomic():
        Barbero.objects.select_for_update().get(pk=barbero.pk)
        if validar_horario:
            libres = horarios_libres(barbero, timezone.localtime(inicio).date(), duracion, clave_sesion)
            if not any(s.inicio == inicio for s in libres):
                raise CupoNoDisponible
        else:
            choque = Cita.objects.filter(
                barbero=barbero, estado__in=Cita.ACTIVAS, inicio__lt=fin, fin__gt=inicio
            ).exists()
            if choque:
                raise CupoNoDisponible
        cita = Cita.objects.create(
            cliente=cliente,
            barbero=barbero,
            inicio=inicio,
            fin=fin,
            precio_total=sum(s.precio for s in servicios),
            origen=origen,
            notas_cliente=notas,
            estado=estado,
        )
        cita.servicios.set(servicios)
        if clave_sesion:
            RetencionCupo.objects.filter(clave_sesion=clave_sesion).delete()
    return cita

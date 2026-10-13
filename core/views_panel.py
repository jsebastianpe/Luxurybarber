"""Panel interno: Hoy, Agenda, Clientes, Caja, Inventario, Comisiones, Marketing, Reportes."""
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import disponibilidad as disp
from . import notificaciones, operaciones as ops
from .models import (Barbero, Bloqueo, Caja, Cita, Cliente, MensajeEnviado, MovimientoCaja,
                     MovimientoInventario, Producto, Servicio)
from .otp import normalizar_telefono
from .roles import ADMIN, BARBERO, RECEPCION, requiere_rol

CFG = settings.BARBERIA
HORA_INI, HORA_FIN = 8, 21   # rango visible de la agenda
PX_MIN = 1.6                  # píxeles por minuto en la agenda


def _fecha(request, nombre="fecha", defecto=None):
    try:
        return date.fromisoformat(request.GET.get(nombre, ""))
    except ValueError:
        return defecto or timezone.localdate()


def _barbero_propio(request):
    return request.user.barbero if request.rol == BARBERO else None


# ---------------- Hoy ----------------
@requiere_rol()
def hoy(request):
    d = timezone.localdate()
    citas = Cita.objects.filter(inicio__date=d).select_related("cliente", "barbero").prefetch_related("servicios")
    propio = _barbero_propio(request)
    if propio:
        citas = citas.filter(barbero=propio)
    activas = [c for c in citas if c.estado != Cita.CANCELADA]
    ahora = timezone.now()
    caja = ops.caja_abierta()
    return render(request, "panel/hoy.html", {
        "kpis": {
            "citas": len(activas),
            "completadas": sum(1 for c in activas if c.estado == Cita.COMPLETADA),
            "ingresos": caja.totales()["ingresos"] if caja and request.rol != BARBERO else None,
            "no_shows": sum(1 for c in activas if c.estado == Cita.NO_SHOW),
        },
        "proximas": [c for c in activas if c.fin >= ahora and c.estado in (Cita.PENDIENTE, Cita.CONFIRMADA, Cita.EN_SILLA)][:8],
        "stock_bajo": Producto.objects.filter(activo=True, stock__lte=F("stock_minimo"))[:6] if request.rol != BARBERO else [],
        "cumpleanos": Cliente.objects.filter(fecha_nacimiento__month=d.month, fecha_nacimiento__day=d.day)[:5],
        "caja": caja,
        "nav": "hoy",
    })


# ---------------- Agenda ----------------
@requiere_rol()
def agenda(request):
    d = _fecha(request)
    barberos = Barbero.objects.filter(activo=True)
    propio = _barbero_propio(request)
    if propio:
        barberos = barberos.filter(pk=propio.pk)
    inicio_vista = timezone.make_aware(datetime.combine(d, time(HORA_INI)))
    columnas = []
    for b in barberos:
        citas = (Cita.objects.filter(barbero=b, inicio__date=d).exclude(estado=Cita.CANCELADA)
                 .select_related("cliente").prefetch_related("servicios"))
        bloqueos = Bloqueo.objects.filter(barbero=b, inicio__date=d)
        turnos = b.horarios.filter(dia_semana=d.weekday())

        def pos(ini, fin):
            top = max(0, (ini - inicio_vista).total_seconds() / 60) * PX_MIN
            alto = max(22, (fin - ini).total_seconds() / 60 * PX_MIN - 4)
            return round(top), round(alto)

        columnas.append({
            "b": b,
            "citas": [(c, *pos(c.inicio, c.fin)) for c in citas],
            "bloqueos": [(x, *pos(x.inicio, x.fin)) for x in bloqueos],
            "libre": not turnos.exists(),
        })
    horas = [{"label": f"{h % 12 or 12} {'a. m.' if h < 12 else 'p. m.'}", "top": round((h - HORA_INI) * 60 * PX_MIN)}
             for h in range(HORA_INI, HORA_FIN)]
    ahora = timezone.localtime()
    linea_ahora = None
    if ahora.date() == d and HORA_INI <= ahora.hour < HORA_FIN:
        linea_ahora = round(((ahora.hour - HORA_INI) * 60 + ahora.minute) * PX_MIN)
    ctx = {
        "fecha": d, "anterior": d - timedelta(days=1), "siguiente": d + timedelta(days=1),
        "columnas": columnas, "horas": horas, "alto_total": round((HORA_FIN - HORA_INI) * 60 * PX_MIN),
        "linea_ahora": linea_ahora, "es_hoy": d == timezone.localdate(),
        "servicios": Servicio.objects.filter(activo=True), "barberos": barberos,
        "nav": "agenda",
    }
    if request.headers.get("HX-Request") and request.GET.get("parcial"):
        return render(request, "panel/_agenda_grid.html", ctx)
    return render(request, "panel/agenda.html", ctx)


@requiere_rol()
def cita_panel(request, pk):
    """Panel lateral (HTMX) con el detalle de la cita y la ficha resumida del cliente."""
    cita = get_object_or_404(Cita.objects.select_related("cliente", "barbero"), pk=pk)
    propio = _barbero_propio(request)
    if propio and cita.barbero_id != propio.id:
        return HttpResponse(status=403)
    return render(request, "panel/_cita_panel.html", {
        "cita": cita, "c": cita.cliente, "medios": MovimientoCaja.MEDIOS, "caja": ops.caja_abierta(),
        "historial": cita.cliente.citas.filter(estado=Cita.COMPLETADA).exclude(pk=cita.pk).order_by("-inicio")[:3],
    })


TRANSICIONES = {
    "confirmar": (Cita.CONFIRMADA, [Cita.PENDIENTE]),
    "en_silla": (Cita.EN_SILLA, [Cita.PENDIENTE, Cita.CONFIRMADA]),
    "completar": (Cita.COMPLETADA, [Cita.EN_SILLA, Cita.CONFIRMADA, Cita.PENDIENTE]),
    "no_show": (Cita.NO_SHOW, [Cita.PENDIENTE, Cita.CONFIRMADA]),
    "cancelar": (Cita.CANCELADA, [Cita.PENDIENTE, Cita.CONFIRMADA]),
}


@require_POST
@requiere_rol()
def cita_estado(request, pk):
    cita = get_object_or_404(Cita, pk=pk)
    propio = _barbero_propio(request)
    if propio and cita.barbero_id != propio.id:
        return HttpResponse(status=403)
    accion = request.POST.get("accion")
    if accion == "cobrar":
        if request.rol == BARBERO:
            return HttpResponse(status=403)
        try:
            ops.cobrar_cita(cita, medio_pago=request.POST.get("medio_pago", "efectivo"),
                            propina=int(request.POST.get("propina") or 0), usuario=request.user)
            messages.success(request, f"Cobrado: {cita.cliente.nombre}")
        except ValueError as e:
            messages.error(request, str(e))
    elif accion in TRANSICIONES:
        nuevo, desde = TRANSICIONES[accion]
        if cita.estado in desde:
            cita.estado = nuevo
            cita.save(update_fields=["estado"])
            if nuevo == Cita.NO_SHOW:
                Cliente.objects.filter(pk=cita.cliente_id).update(no_shows=F("no_shows") + 1)
            if nuevo == Cita.COMPLETADA:
                Cliente.objects.filter(pk=cita.cliente_id).update(ultima_visita=cita.fin)
    resp = HttpResponse(status=204)
    resp["HX-Trigger"] = "agenda-cambio"
    if not request.headers.get("HX-Request"):
        return redirect(request.POST.get("next") or "panel:agenda")
    return resp


@require_POST
@requiere_rol(ADMIN, RECEPCION)
def cita_nueva(request):
    """Cita creada desde recepción (reserva telefónica o cliente sin reserva)."""
    telefono = normalizar_telefono(request.POST.get("telefono", ""))
    nombre = request.POST.get("nombre", "").strip()
    servicios = list(Servicio.objects.filter(id__in=request.POST.getlist("servicios")))
    barbero = Barbero.objects.filter(pk=request.POST.get("barbero")).first()
    try:
        inicio = timezone.make_aware(datetime.fromisoformat(f"{request.POST['fecha']}T{request.POST['hora']}"))
    except (KeyError, ValueError):
        inicio = None
    if not (telefono and nombre and servicios and barbero and inicio):
        messages.error(request, "Completa nombre, celular válido, servicios, barbero y hora.")
        return redirect(request.POST.get("next") or "panel:agenda")
    cliente, _ = Cliente.objects.get_or_create(telefono=telefono, defaults={"nombre": nombre})
    walkin = request.POST.get("walkin") == "1"
    try:
        cita = disp.crear_cita(cliente=cliente, barbero=barbero, servicios=servicios, inicio=inicio,
                               origen="walkin" if walkin else "panel", validar_horario=False,
                               estado=Cita.EN_SILLA if walkin else Cita.CONFIRMADA)
    except disp.CupoNoDisponible:
        messages.error(request, f"{barbero.nombre} ya tiene una cita en ese horario.")
    else:
        if not walkin:
            notificaciones.confirmacion(cita)
        messages.success(request, f"Cita creada para {cliente.nombre}.")
    return redirect(f"{request.POST.get('next') or '/panel/agenda/'}")


@require_POST
@requiere_rol()
def bloqueo_nuevo(request):
    b = _barbero_propio(request) or get_object_or_404(Barbero, pk=request.POST.get("barbero"))
    try:
        f = request.POST["fecha"]
        ini = timezone.make_aware(datetime.fromisoformat(f"{f}T{request.POST['desde']}"))
        fin = timezone.make_aware(datetime.fromisoformat(f"{f}T{request.POST['hasta']}"))
        assert fin > ini
    except (KeyError, ValueError, AssertionError):
        messages.error(request, "Revisa el rango de horas del bloqueo.")
    else:
        Bloqueo.objects.create(barbero=b, inicio=ini, fin=fin, motivo=request.POST.get("motivo") or "Bloqueado")
        messages.success(request, "Horario bloqueado.")
    return redirect(request.POST.get("next") or "panel:agenda")


@require_POST
@requiere_rol()
def bloqueo_borrar(request, pk):
    q = Bloqueo.objects.filter(pk=pk)
    if _barbero_propio(request):
        q = q.filter(barbero=_barbero_propio(request))
    q.delete()
    return redirect(request.POST.get("next") or "panel:agenda")


# ---------------- Clientes ----------------
@requiere_rol()
def clientes(request):
    q = request.GET.get("q", "").strip()
    filtro = request.GET.get("filtro", "")
    qs = Cliente.objects.annotate(visitas=Count("citas", filter=Q(citas__estado=Cita.COMPLETADA)))
    propio = _barbero_propio(request)
    if propio:
        qs = qs.filter(citas__barbero=propio).distinct()
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(telefono__icontains=q))
    ahora = timezone.now()
    if filtro == "inactivos":
        qs = qs.filter(ultima_visita__lt=ahora - timedelta(days=CFG["INACTIVO_DIAS"][0]))
    elif filtro == "frecuentes":
        qs = qs.filter(visitas__gte=5)
    elif filtro == "nuevos":
        qs = qs.filter(creado__gte=ahora - timedelta(days=30))
    return render(request, "panel/clientes.html", {
        "clientes": qs.order_by("-ultima_visita")[:200], "q": q, "filtro": filtro, "nav": "clientes",
    })


@requiere_rol()
def cliente_ficha(request, pk):
    c = get_object_or_404(Cliente, pk=pk)
    propio = _barbero_propio(request)
    if propio and not c.citas.filter(barbero=propio).exists():
        return HttpResponse(status=403)
    if request.method == "POST":
        for campo in ("pref_maquina", "pref_estilo", "pref_barba", "notas"):
            if campo in request.POST:
                setattr(c, campo, request.POST[campo].strip())
        c.save()
        if request.FILES.get("foto"):
            from .models import FotoReferencia
            FotoReferencia.objects.create(cliente=c, archivo=request.FILES["foto"], es_resultado=True,
                                          descripcion=request.POST.get("descripcion", "Resultado del corte"))
        messages.success(request, "Ficha actualizada.")
        return redirect("panel:cliente_ficha", pk=pk)
    citas = c.citas.select_related("barbero").prefetch_related("servicios").order_by("-inicio")
    gastado = citas.filter(estado=Cita.COMPLETADA).aggregate(t=Sum("precio_total"))["t"] or 0
    return render(request, "panel/cliente_ficha.html", {
        "c": c, "citas": citas[:30], "gastado": gastado,
        "visitas": citas.filter(estado=Cita.COMPLETADA).count(), "nav": "clientes",
    })


# ---------------- Caja ----------------
@requiere_rol(ADMIN, RECEPCION)
def caja(request):
    actual = ops.caja_abierta()
    if request.method == "POST":
        accion = request.POST.get("accion")
        try:
            if accion == "abrir" and not actual:
                Caja.objects.create(abierta_por=request.user, base_inicial=int(request.POST.get("base") or 0))
                messages.success(request, "Caja abierta.")
            elif accion == "gasto" and actual:
                MovimientoCaja.objects.create(
                    caja=actual, tipo=MovimientoCaja.EGRESO, concepto=request.POST.get("concepto") or "Gasto",
                    monto=int(request.POST["monto"]), medio_pago=request.POST.get("medio_pago", "efectivo"),
                    usuario=request.user,
                )
                messages.success(request, "Gasto registrado.")
            elif accion == "venta" and actual:
                p = get_object_or_404(Producto, pk=request.POST.get("producto"))
                ops.registrar_inventario(
                    p, MovimientoInventario.VENTA, int(request.POST.get("cantidad") or 1),
                    barbero=Barbero.objects.filter(pk=request.POST.get("barbero")).first(),
                    usuario=request.user, medio_pago=request.POST.get("medio_pago", "efectivo"),
                )
                messages.success(request, f"Venta registrada: {p.nombre}")
            elif accion == "cerrar" and actual:
                actual.efectivo_contado = int(request.POST.get("contado") or 0)
                actual.nota_cierre = request.POST.get("nota", "")[:200]
                actual.cerrada_en = timezone.now()
                actual.save()
                dif = actual.efectivo_contado - actual.totales()["efectivo_esperado"]
                messages.success(request, f"Caja cerrada. Diferencia en efectivo: {dif:+,}".replace(",", "."))
        except (ValueError, KeyError) as e:
            messages.error(request, f"No se pudo registrar: {e}")
        return redirect("panel:caja")
    por_cobrar = []
    if actual:
        por_cobrar = (Cita.objects.filter(inicio__date=timezone.localdate(), pagada=False,
                                          estado__in=[Cita.EN_SILLA, Cita.COMPLETADA, Cita.CONFIRMADA])
                      .select_related("cliente", "barbero").prefetch_related("servicios"))
    return render(request, "panel/caja.html", {
        "caja": actual, "totales": actual.totales() if actual else None,
        "movimientos": actual.movimientos.select_related("barbero")[:50] if actual else [],
        "por_cobrar": por_cobrar, "medios": MovimientoCaja.MEDIOS,
        "productos": Producto.objects.filter(activo=True, para_venta=True, stock__gt=0),
        "barberos": Barbero.objects.filter(activo=True),
        "historial": Caja.objects.filter(cerrada_en__isnull=False)[:10],
        "nav": "caja",
    })


# ---------------- Inventario ----------------
@requiere_rol()
def inventario(request):
    if request.method == "POST":
        p = get_object_or_404(Producto, pk=request.POST.get("producto"))
        tipo = request.POST.get("tipo")
        if request.rol == BARBERO:
            tipo = MovimientoInventario.USO  # el barbero solo registra consumo
        if tipo not in dict(MovimientoInventario.TIPOS):
            messages.error(request, "Tipo de movimiento inválido.")
        else:
            try:
                ops.registrar_inventario(
                    p, tipo, int(request.POST.get("cantidad") or 1),
                    barbero=_barbero_propio(request) or Barbero.objects.filter(pk=request.POST.get("barbero")).first(),
                    usuario=request.user, nota=request.POST.get("nota", ""),
                    medio_pago=request.POST.get("medio_pago", "efectivo"),
                )
                messages.success(request, f"Movimiento registrado: {p.nombre}")
            except ValueError as e:
                messages.error(request, str(e))
        return redirect("panel:inventario")
    productos = Producto.objects.filter(activo=True)
    valor = sum(p.stock * p.costo for p in productos)
    return render(request, "panel/inventario.html", {
        "productos": productos, "valor": valor,
        "bajos": [p for p in productos if p.stock_bajo],
        "movimientos": MovimientoInventario.objects.select_related("producto", "barbero")[:25],
        "tipos": MovimientoInventario.TIPOS, "barberos": Barbero.objects.filter(activo=True),
        "medios": MovimientoCaja.MEDIOS, "nav": "inventario",
    })


# ---------------- Comisiones ----------------
@requiere_rol()
def comisiones(request):
    hoy_ = timezone.localdate()
    # Por defecto: quincena actual
    defecto_desde = hoy_.replace(day=1) if hoy_.day <= 15 else hoy_.replace(day=16)
    desde = _fecha(request, "desde", defecto_desde)
    hasta = _fecha(request, "hasta", hoy_)
    filas = ops.comisiones(desde, hasta, barbero=_barbero_propio(request))
    return render(request, "panel/comisiones.html", {
        "filas": filas, "desde": desde, "hasta": hasta,
        "total": sum(f["total_pagar"] for f in filas), "nav": "comisiones",
    })


# ---------------- Marketing ----------------
@requiere_rol(ADMIN)
def marketing(request):
    dias = int(request.GET.get("dias") or CFG["INACTIVO_DIAS"][0])
    limite = timezone.now() - timedelta(days=dias)
    inactivos = (Cliente.objects.filter(ultima_visita__lt=limite, acepta_whatsapp=True)
                 .exclude(citas__inicio__gte=timezone.now(), citas__estado__in=[Cita.PENDIENTE, Cita.CONFIRMADA])
                 .order_by("ultima_visita"))
    plantilla = ("¡{nombre}, te extrañamos! Hace {dias} días no te vemos. Tienes {puntos} puntos esperando. "
                 "Reserva aquí: {enlace}")
    if request.method == "POST":
        ids = request.POST.getlist("clientes")
        texto = request.POST.get("mensaje") or plantilla
        enviados = 0
        for c in Cliente.objects.filter(id__in=ids):
            notificaciones.reactivacion(c, texto)
            enviados += 1
        messages.success(request, f"Mensaje enviado a {enviados} cliente(s).")
        return redirect(f"{request.path}?dias={dias}")
    top_puntos = Cliente.objects.order_by("-puntos")[:8]
    return render(request, "panel/marketing.html", {
        "inactivos": inactivos[:100], "dias": dias, "opciones": CFG["INACTIVO_DIAS"], "plantilla": plantilla,
        "mensajes": MensajeEnviado.objects.select_related("cliente")[:20], "top_puntos": top_puntos,
        "nav": "marketing",
    })


# ---------------- Reportes ----------------
@requiere_rol(ADMIN)
def reportes(request):
    hasta = _fecha(request, "hasta")
    desde = _fecha(request, "desde", hasta - timedelta(days=29))
    data = ops.reportes(desde, hasta)
    return render(request, "panel/reportes.html", {
        **data,
        "desde": desde, "hasta": hasta,
        "chart": {
            "heatmap": data["heatmap"], "horas": data["horas"],
            "dias": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
            "servicios": [s["nombre"] for s in data["servicios"]][:8],
            "ingresos": [s["ingreso"] for s in data["servicios"]][:8],
        },
        "nav": "reportes",
    })

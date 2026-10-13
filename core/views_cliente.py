"""Vistas del cliente final: landing, reserva en 4 pasos, acceso por código, mis citas y perfil."""
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import disponibilidad as disp
from . import notificaciones, otp
from .models import Barbero, Cita, Cliente, FotoReferencia, RetencionCupo, Servicio

CFG = settings.BARBERIA


# ---------------- utilidades ----------------
def cliente_actual(request):
    cid = request.session.get("cliente_id")
    return Cliente.objects.filter(pk=cid).first() if cid else None


def _clave(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def _reserva(request):
    return request.session.setdefault("reserva", {})


def _guardar(request, **datos):
    r = _reserva(request)
    r.update(datos)
    request.session["reserva"] = r
    request.session.modified = True


def _servicios_elegidos(request):
    ids = _reserva(request).get("servicios") or []
    return list(Servicio.objects.filter(id__in=ids, activo=True))


def _resumen(request):
    servicios = _servicios_elegidos(request)
    r = _reserva(request)
    barbero = None
    if r.get("barbero_asignado"):
        barbero = Barbero.objects.filter(pk=r["barbero_asignado"]).first()
    elif r.get("barbero") not in (None, "any"):
        barbero = Barbero.objects.filter(pk=r["barbero"]).first()
    inicio = datetime.fromisoformat(r["inicio"]) if r.get("inicio") else None
    duracion = sum(s.duracion_min for s in servicios)
    return {
        "servicios": servicios,
        "nombres": " + ".join(s.nombre for s in servicios),
        "duracion": duracion,
        "total": sum(s.precio for s in servicios),
        "barbero": barbero,
        "cualquiera": r.get("barbero") == "any",
        "inicio": inicio,
        "fin": inicio + timedelta(minutes=duracion) if inicio else None,
    }


def _barberos_seleccion(request):
    r = _reserva(request)
    servicios_ids = r.get("servicios") or []
    if r.get("barbero") == "any":
        return list(disp.barberos_para(servicios_ids))
    return list(Barbero.objects.filter(pk=r.get("barbero"), activo=True))


# ---------------- páginas públicas ----------------
def inicio(request):
    return render(request, "cliente/inicio.html", {
        "servicios": Servicio.objects.filter(activo=True),
        "barberos": Barbero.objects.filter(activo=True),
        "cliente": cliente_actual(request),
        "nav": "inicio",
    })


def barbero_detalle(request, slug):
    b = get_object_or_404(Barbero, slug=slug, activo=True)
    return render(request, "cliente/barbero.html", {"b": b, "nav": "inicio"})


# ---------------- reserva: paso 1 ----------------
def reservar_servicio(request):
    if request.method == "POST":
        ids = [int(i) for i in request.POST.getlist("servicios") if i.isdigit()]
        if not ids:
            messages.error(request, "Elige al menos un servicio.")
            return redirect("cliente:reservar_servicio")
        request.session["reserva"] = {"servicios": ids}
        RetencionCupo.objects.filter(clave_sesion=_clave(request)).delete()
        return redirect("cliente:reservar_barbero")

    cliente = cliente_actual(request)
    ultima = None
    if cliente:
        ultima = cliente.citas.filter(estado=Cita.COMPLETADA).order_by("-inicio").first()
    servicios = Servicio.objects.filter(activo=True)
    categorias = [(k, v, [s for s in servicios if s.categoria == k]) for k, v in Servicio.CATEGORIAS]
    return render(request, "cliente/reservar_servicio.html", {
        "categorias": [c for c in categorias if c[2]],
        "seleccion": _reserva(request).get("servicios") or [int(x) for x in request.GET.getlist("s") if x.isdigit()],
        "ultima": ultima,
        "paso": 1,
        "nav": "reservar",
    })


def repetir(request):
    cliente = cliente_actual(request)
    if not cliente:
        return redirect("cliente:reservar_servicio")
    ultima = cliente.citas.filter(estado=Cita.COMPLETADA).order_by("-inicio").first()
    if not ultima:
        return redirect("cliente:reservar_servicio")
    request.session["reserva"] = {
        "servicios": list(ultima.servicios.values_list("id", flat=True)),
        "barbero": ultima.barbero_id if ultima.barbero.activo else "any",
    }
    return redirect("cliente:reservar_horario")


# ---------------- reserva: paso 2 ----------------
def reservar_barbero(request):
    servicios = _servicios_elegidos(request)
    if not servicios:
        return redirect("cliente:reservar_servicio")
    eleccion = request.GET.get("barbero")
    if eleccion:
        if eleccion != "any" and not Barbero.objects.filter(pk=eleccion, activo=True).exists():
            raise Http404
        _guardar(request, barbero=eleccion if eleccion == "any" else int(eleccion), inicio=None,
                 barbero_asignado=None)
        return redirect("cliente:reservar_horario")

    duracion = sum(s.duracion_min for s in servicios)
    cliente = cliente_actual(request)
    tarjetas = []
    for b in disp.barberos_para([s.id for s in servicios]):
        tarjetas.append({"b": b, "proximo": disp.proximo_cupo(b, duracion),
                         "habitual": cliente and cliente.barbero_preferido_id == b.id})
    tarjetas.sort(key=lambda t: (not t["habitual"], t["proximo"] is None))
    return render(request, "cliente/reservar_barbero.html", {
        "tarjetas": tarjetas,
        "resumen": _resumen(request),
        "paso": 2,
        "nav": "reservar",
    })


# ---------------- reserva: paso 3 ----------------
def reservar_horario(request):
    servicios = _servicios_elegidos(request)
    r = _reserva(request)
    if not servicios or not r.get("barbero"):
        return redirect("cliente:reservar_servicio")
    barberos = _barberos_seleccion(request)
    duracion = sum(s.duracion_min for s in servicios)
    error = None

    if request.method == "POST":
        valor = request.POST.get("slot", "")
        try:
            bid, iso_inicio = valor.split("|", 1)
            barbero = next(b for b in barberos if b.id == int(bid))
            inicio_dt = datetime.fromisoformat(iso_inicio)
            disp.retener(barbero, inicio_dt, duracion, _clave(request))
        except (ValueError, StopIteration):
            error = "Elige una hora de la lista."
        except disp.CupoNoDisponible:
            error = "Esa hora acaba de reservarse. Elige otra."
        else:
            _guardar(request, inicio=inicio_dt.isoformat(), barbero_asignado=barbero.id)
            return redirect("cliente:reservar_confirmar")

    hoy = timezone.localdate()
    dias = disp.resumen_dias(barberos, duracion, hoy, CFG["DIAS_VISIBLES"], _clave(request))
    try:
        fecha = date.fromisoformat(request.GET.get("fecha", ""))
    except ValueError:
        fecha = next((d["fecha"] for d in dias if d["libres"]), hoy)
    primer_libre = next((d["fecha"] for d in dias if d["libres"]), None)
    return render(request, "cliente/reservar_horario.html", {
        "dias": dias,
        "fecha": fecha,
        "primer_libre": primer_libre,
        "grupos": _grupos(barberos, fecha, duracion, _clave(request)),
        "resumen": _resumen(request),
        "error": error,
        "paso": 3,
        "nav": "reservar",
    })


def _grupos(barberos, fecha, duracion, clave):
    slots = disp.horarios_combinados(barberos, fecha, duracion, clave)
    grupos = {"Mañana": [], "Tarde": [], "Noche": []}
    for s in slots:
        h = timezone.localtime(s.inicio).hour
        grupos["Mañana" if h < 12 else "Tarde" if h < 18 else "Noche"].append(s)
    return [(k, v) for k, v in grupos.items() if v]


def horario_slots(request):
    """Fragmento HTMX con las horas libres de un día (se refresca cada 20 s)."""
    servicios = _servicios_elegidos(request)
    if not servicios:
        return HttpResponse(status=204)
    try:
        fecha = date.fromisoformat(request.GET.get("fecha", ""))
    except ValueError:
        fecha = timezone.localdate()
    duracion = sum(s.duracion_min for s in servicios)
    return render(request, "cliente/_slots.html", {
        "grupos": _grupos(_barberos_seleccion(request), fecha, duracion, _clave(request)),
        "fecha": fecha,
    })


# ---------------- reserva: paso 4 ----------------
def reservar_confirmar(request):
    r = _reserva(request)
    resumen = _resumen(request)
    if not resumen["servicios"] or not resumen["inicio"] or not resumen["barbero"]:
        return redirect("cliente:reservar_servicio")
    retencion = RetencionCupo.objects.filter(clave_sesion=_clave(request)).first()
    cliente = cliente_actual(request)
    errores = {}
    datos = {"nombre": cliente.nombre if cliente else "", "telefono": cliente.telefono if cliente else "", "notas": ""}

    if request.method == "POST":
        datos = {k: request.POST.get(k, "").strip() for k in ("nombre", "telefono", "notas", "codigo")}
        telefono = otp.normalizar_telefono(datos["telefono"])
        if not datos["nombre"]:
            errores["nombre"] = "Escribe tu nombre."
        if not telefono:
            errores["telefono"] = "Escribe un celular válido (10 dígitos)."
        if not request.POST.get("acepta"):
            errores["acepta"] = "Necesitamos tu autorización para enviarte la confirmación."
        verificado = cliente is not None and telefono == cliente.telefono
        if telefono and not verificado and not errores:
            err = otp.verificar(telefono, datos.get("codigo"))
            if err:
                errores["codigo"] = err
        if not errores:
            c, creado = Cliente.objects.get_or_create(telefono=telefono, defaults={"nombre": datos["nombre"]})
            if creado:
                c.puntos = CFG["PUNTOS_BIENVENIDA"]
                c.save(update_fields=["puntos"])
            try:
                cita = disp.crear_cita(
                    cliente=c, barbero=resumen["barbero"], servicios=resumen["servicios"], inicio=resumen["inicio"],
                    clave_sesion=_clave(request), notas=datos["notas"],
                )
            except disp.CupoNoDisponible:
                _guardar(request, inicio=None, barbero_asignado=None)
                messages.error(request, "Esa hora se acaba de ocupar. Elige otra; lo demás se mantiene.")
                return redirect("cliente:reservar_horario")
            foto = request.FILES.get("foto")
            if foto:
                FotoReferencia.objects.create(cliente=c, archivo=foto, descripcion="Referencia de la reserva")
            if not c.barbero_preferido_id:
                c.barbero_preferido = cita.barbero
                c.save(update_fields=["barbero_preferido"])
            notificaciones.confirmacion(cita)
            request.session["cliente_id"] = c.id
            request.session["reserva"] = {}
            request.session["nuevo"] = creado
            return redirect("cliente:reserva_lista", token=cita.token)

    return render(request, "cliente/reservar_confirmar.html", {
        "resumen": resumen,
        "retencion": retencion,
        "cliente": cliente,
        "datos": datos,
        "errores": errores,
        "cancelacion_horas": CFG["CANCELACION_HORAS"],
        "paso": 4,
        "nav": "reservar",
        "debug": settings.DEBUG,
    })


@require_POST
def enviar_codigo(request):
    """HTMX: envía el código de 6 dígitos al celular."""
    telefono = otp.normalizar_telefono(request.POST.get("telefono", ""))
    if not telefono:
        return render(request, "cliente/_otp.html", {"error": "Escribe un celular válido (10 dígitos)."})
    reg, error = otp.enviar_codigo(telefono)
    return render(request, "cliente/_otp.html", {
        "enviado": True, "telefono": telefono, "error": error,
        "codigo_debug": reg.codigo if settings.DEBUG else None,
    })


def reserva_lista(request, token):
    cita = get_object_or_404(Cita, token=token)
    nuevo = request.session.pop("nuevo", False)
    return render(request, "cliente/reserva_lista.html", {
        "cita": cita, "nuevo": nuevo, "puntos_bienvenida": CFG["PUNTOS_BIENVENIDA"], "nav": "reservar",
    })


def cita_ics(request, token):
    cita = get_object_or_404(Cita, token=token)
    f = "%Y%m%dT%H%M%SZ"
    ics = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Barberia//ES", "BEGIN:VEVENT",
        f"UID:{cita.token}@barberia",
        f"DTSTAMP:{timezone.now().astimezone(dt_timezone.utc):{f}}",
        f"DTSTART:{cita.inicio.astimezone(dt_timezone.utc):{f}}",
        f"DTEND:{cita.fin.astimezone(dt_timezone.utc):{f}}",
        f"SUMMARY:{cita.nombres_servicios} - {CFG['NOMBRE']}",
        f"LOCATION:{CFG['DIRECCION']}",
        f"DESCRIPTION:Con {cita.barbero.nombre}",
        "END:VEVENT", "END:VCALENDAR", "",
    ])
    resp = HttpResponse(ics, content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="cita.ics"'
    return resp


def un_toque(request, token):
    """Enlace de los recordatorios: confirmar o cancelar sin iniciar sesión."""
    cita = get_object_or_404(Cita.objects.select_related("barbero", "cliente"), token=token)
    if request.method == "POST" and cita.es_futura:
        accion = request.POST.get("accion")
        if accion == "confirmar" and cita.estado in (Cita.PENDIENTE, Cita.CONFIRMADA):
            cita.estado = Cita.CONFIRMADA
            cita.save(update_fields=["estado"])
            messages.success(request, "¡Gracias! Tu cita está confirmada.")
        elif accion == "cancelar" and cita.estado in (Cita.PENDIENTE, Cita.CONFIRMADA):
            cita.estado = Cita.CANCELADA
            cita.save(update_fields=["estado"])
            notificaciones.cancelacion(cita)
            messages.success(request, "Cancelamos tu cita y liberamos el horario.")
        return redirect("cliente:un_toque", token=token)
    return render(request, "cliente/un_toque.html", {"cita": cita, "nav": "citas"})


# ---------------- acceso ----------------
def acceso(request):
    siguiente = request.GET.get("next") or request.POST.get("next") or reverse("cliente:mis_citas")
    if not siguiente.startswith("/"):
        siguiente = reverse("cliente:mis_citas")
    ctx = {"next": siguiente, "nav": "perfil"}
    if request.method == "POST":
        telefono = otp.normalizar_telefono(request.POST.get("telefono", ""))
        codigo = request.POST.get("codigo")
        if not telefono:
            ctx["error"] = "Escribe un celular válido (10 dígitos)."
        elif not codigo:
            reg, err = otp.enviar_codigo(telefono)
            ctx.update(paso="codigo", telefono=telefono, error=err,
                       codigo_debug=reg.codigo if settings.DEBUG else None)
        else:
            err = otp.verificar(telefono, codigo)
            if err:
                ctx.update(paso="codigo", telefono=telefono, error=err)
            else:
                cliente = Cliente.objects.filter(telefono=telefono).first()
                if not cliente:
                    messages.info(request, "Aún no tienes citas con nosotros. ¡Reserva la primera!")
                    return redirect("cliente:reservar_servicio")
                request.session["cliente_id"] = cliente.id
                return redirect(siguiente)
    return render(request, "cliente/acceso.html", ctx)


def salir(request):
    request.session.pop("cliente_id", None)
    return redirect("cliente:inicio")


def _requiere_cliente(view):
    def _w(request, *a, **kw):
        c = cliente_actual(request)
        if not c:
            return redirect(f"{reverse('cliente:acceso')}?next={request.path}")
        request.cliente = c
        return view(request, *a, **kw)
    _w.__name__ = view.__name__
    return _w


@_requiere_cliente
def mis_citas(request):
    c = request.cliente
    ahora = timezone.now()
    citas = c.citas.select_related("barbero").prefetch_related("servicios")
    return render(request, "cliente/mis_citas.html", {
        "proximas": citas.filter(inicio__gte=ahora, estado__in=[Cita.PENDIENTE, Cita.CONFIRMADA]),
        "pasadas": citas.filter(inicio__lt=ahora).order_by("-inicio")[:20],
        "cliente": c,
        "nav": "citas",
    })


@_requiere_cliente
def cita_detalle(request, token):
    cita = get_object_or_404(Cita, token=token, cliente=request.cliente)
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion in ("cancelar", "reprogramar") and cita.es_futura and cita.estado in (Cita.PENDIENTE, Cita.CONFIRMADA):
            cita.estado = Cita.CANCELADA
            cita.save(update_fields=["estado"])
            if accion == "reprogramar":
                request.session["reserva"] = {
                    "servicios": list(cita.servicios.values_list("id", flat=True)),
                    "barbero": cita.barbero_id,
                }
                messages.info(request, "Elige el nuevo horario. Tu cita anterior quedó liberada.")
                return redirect("cliente:reservar_horario")
            notificaciones.cancelacion(cita)
            messages.success(request, "Cita cancelada.")
            return redirect("cliente:mis_citas")
    return render(request, "cliente/cita_detalle.html", {"cita": cita, "nav": "citas",
                                                         "cancelacion_horas": CFG["CANCELACION_HORAS"]})


@_requiere_cliente
def perfil(request):
    c = request.cliente
    if request.method == "POST":
        if request.FILES.get("foto"):
            FotoReferencia.objects.create(
                cliente=c, archivo=request.FILES["foto"], descripcion=request.POST.get("descripcion", "")[:120]
            )
            messages.success(request, "Foto guardada.")
        else:
            for campo in ("nombre", "email", "pref_maquina", "pref_estilo", "pref_barba"):
                if campo in request.POST:
                    setattr(c, campo, request.POST[campo].strip()[:120])
            c.acepta_whatsapp = bool(request.POST.get("acepta_whatsapp"))
            bp = request.POST.get("barbero_preferido")
            c.barbero_preferido = Barbero.objects.filter(pk=bp).first() if bp else None
            c.save()
            messages.success(request, "Preferencias guardadas. Tu barbero las verá antes de tu cita.")
        return redirect("cliente:perfil")
    return render(request, "cliente/perfil.html", {
        "cliente": c, "barberos": Barbero.objects.filter(activo=True), "nav": "perfil",
    })


@_requiere_cliente
def borrar_foto(request, pk):
    if request.method == "POST":
        FotoReferencia.objects.filter(pk=pk, cliente=request.cliente).delete()
    return redirect("cliente:perfil")


RECOMPENSAS = [
    {"puntos": 150, "nombre": "Lavado y masaje capilar"},
    {"puntos": 300, "nombre": "Arreglo de barba gratis"},
    {"puntos": 500, "nombre": "Corte gratis"},
]


@_requiere_cliente
def puntos(request):
    c = request.cliente
    historial = c.citas.filter(estado=Cita.COMPLETADA).order_by("-inicio")[:15]
    from .operaciones import puntos_por
    return render(request, "cliente/puntos.html", {
        "cliente": c,
        "recompensas": RECOMPENSAS,
        "historial": [(h, puntos_por(h.precio_total)) for h in historial],
        "nav": "perfil",
    })

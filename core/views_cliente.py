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
<<<<<<< HEAD
from . import privacidad as priv
from .archivos import validar_archivo
from .models import Barbero, Cita, Cliente, Consentimiento, FotoReferencia, RetencionCupo, Servicio
=======
from .models import Barbero, Cita, Cliente, FotoReferencia, RetencionCupo, Servicio
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad

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

<<<<<<< HEAD
    ya_autorizado = bool(cliente and not cliente.requiere_reaceptar)
    if request.method == "POST":
        datos = {k: request.POST.get(k, "").strip() for k in ("nombre", "telefono", "notas", "codigo")}
        marcas = {k: bool(request.POST.get(k)) for k in ("acepta_datos", "acepta_terminos", "acepta_fotos",
                                                          "acepta_marketing")}
        datos.update(marcas)
=======
    if request.method == "POST":
        datos = {k: request.POST.get(k, "").strip() for k in ("nombre", "telefono", "notas", "codigo")}
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
        telefono = otp.normalizar_telefono(datos["telefono"])
        if not datos["nombre"]:
            errores["nombre"] = "Escribe tu nombre."
        if not telefono:
            errores["telefono"] = "Escribe un celular válido (10 dígitos)."
<<<<<<< HEAD
        if not ya_autorizado or telefono != cliente.telefono:
            if not marcas["acepta_datos"]:
                errores["acepta_datos"] = "Para reservar necesitamos tu autorización para tratar tus datos y confirmar que eres mayor de edad."
            if not marcas["acepta_terminos"]:
                errores["acepta_terminos"] = "Debes aceptar los términos y condiciones."
        foto = request.FILES.get("foto")
        if foto:
            err_foto = validar_archivo(foto)
            if err_foto:
                errores["foto"] = err_foto
            elif not (marcas["acepta_fotos"] or (cliente and cliente.acepta_sensibles and telefono == cliente.telefono)):
                errores["foto"] = "Para guardar la foto necesitamos tu autorización expresa (casilla de fotografías). Si no la das, quita la foto."
=======
        if not request.POST.get("acepta"):
            errores["acepta"] = "Necesitamos tu autorización para enviarte la confirmación."
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
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
<<<<<<< HEAD
            if not (ya_autorizado and verificado):
                # Desmarcar una casilla opcional aquí no revoca lo ya autorizado: eso se hace en "Mis datos".
                priv.aplicar_autorizaciones(
                    c, sensibles=marcas["acepta_fotos"] or c.acepta_sensibles,
                    marketing=marcas["acepta_marketing"] or c.acepta_marketing, request=request)
            elif marcas["acepta_fotos"] and not c.acepta_sensibles:
                priv.registrar_consentimiento(c, Consentimiento.SENSIBLES, True, request)
                c.acepta_sensibles = True
                c.save(update_fields=["acepta_sensibles"])
            try:
                cita = disp.crear_cita(
                    cliente=c, barbero=resumen["barbero"], servicios=resumen["servicios"], inicio=resumen["inicio"],
                    clave_sesion=_clave(request), notas=datos["notas"][:240],
=======
            try:
                cita = disp.crear_cita(
                    cliente=c, barbero=resumen["barbero"], servicios=resumen["servicios"], inicio=resumen["inicio"],
                    clave_sesion=_clave(request), notas=datos["notas"],
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
                )
            except disp.CupoNoDisponible:
                _guardar(request, inicio=None, barbero_asignado=None)
                messages.error(request, "Esa hora se acaba de ocupar. Elige otra; lo demás se mantiene.")
                return redirect("cliente:reservar_horario")
<<<<<<< HEAD
            if foto and c.acepta_sensibles:
=======
            foto = request.FILES.get("foto")
            if foto:
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
                FotoReferencia.objects.create(cliente=c, archivo=foto, descripcion="Referencia de la reserva")
            if not c.barbero_preferido_id:
                c.barbero_preferido = cita.barbero
                c.save(update_fields=["barbero_preferido"])
            notificaciones.confirmacion(cita)
<<<<<<< HEAD
            request.session.cycle_key()
=======
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
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
<<<<<<< HEAD
        "ya_autorizado": ya_autorizado,
        "texto_autorizacion": priv.texto_autorizacion(),
        "texto_sensibles": priv.texto_sensibles(),
        "texto_marketing": priv.texto_marketing(),
=======
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
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
<<<<<<< HEAD
    reg, error, debug = otp.enviar_codigo(telefono, priv.ip_de(request))
    if reg:
        request.session["otp_id"] = reg.pk  # solo el servidor sabe qué registro consultar
    return render(request, "cliente/_otp.html", {
        "enviado": reg is not None and not (reg.estado == "fallido"), "telefono": telefono, "error": error,
        "codigo_debug": debug, "reg": reg, "whatsapp": settings.MENSAJES_BACKEND == "whatsapp",
    })


def estado_codigo(request):
    """HTMX: estado de entrega del último código (lo actualiza el webhook de Meta)."""
    from .models import CodigoVerificacion
    reg = CodigoVerificacion.objects.filter(pk=request.session.get("otp_id")).first()
    if reg is None:
        return HttpResponse(status=204)
    return render(request, "cliente/_otp_estado.html", {"reg": reg, "whatsapp": settings.MENSAJES_BACKEND == "whatsapp"})


=======
    reg, error = otp.enviar_codigo(telefono)
    return render(request, "cliente/_otp.html", {
        "enviado": True, "telefono": telefono, "error": error,
        "codigo_debug": reg.codigo if settings.DEBUG else None,
    })


>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
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
<<<<<<< HEAD
            reg, err, debug = otp.enviar_codigo(telefono, priv.ip_de(request))
            if reg:
                request.session["otp_id"] = reg.pk
            if reg is None or reg.estado == "fallido":
                ctx.update(error=err)
            else:
                ctx.update(paso="codigo", telefono=telefono, error=err, codigo_debug=debug, reg=reg,
                           whatsapp=settings.MENSAJES_BACKEND == "whatsapp")
=======
            reg, err = otp.enviar_codigo(telefono)
            ctx.update(paso="codigo", telefono=telefono, error=err,
                       codigo_debug=reg.codigo if settings.DEBUG else None)
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
        else:
            err = otp.verificar(telefono, codigo)
            if err:
                ctx.update(paso="codigo", telefono=telefono, error=err)
            else:
<<<<<<< HEAD
                cliente = Cliente.objects.filter(telefono=telefono, anonimizado_en__isnull=True).first()
                if not cliente:
                    messages.info(request, "Aún no tienes citas con nosotros. ¡Reserva la primera!")
                    return redirect("cliente:reservar_servicio")
                request.session.cycle_key()
=======
                cliente = Cliente.objects.filter(telefono=telefono).first()
                if not cliente:
                    messages.info(request, "Aún no tienes citas con nosotros. ¡Reserva la primera!")
                    return redirect("cliente:reservar_servicio")
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
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
<<<<<<< HEAD
        # Cambio sustancial de la política: se informa y se pide aceptar la nueva versión (Decreto 1074, 2.2.2.25.2.2)
        if c.requiere_reaceptar and view.__name__ not in ("reaceptar_politica", "descargar_datos", "eliminar_cuenta"):
            return redirect(f"{reverse('cliente:reaceptar')}?next={request.path}")
=======
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
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
<<<<<<< HEAD
            if not c.acepta_sensibles:
                messages.error(request, "Primero autoriza el uso de fotografías en «Mis datos».")
            else:
                err = validar_archivo(request.FILES["foto"])
                if err:
                    messages.error(request, err)
                else:
                    FotoReferencia.objects.create(
                        cliente=c, archivo=request.FILES["foto"], descripcion=request.POST.get("descripcion", "")[:120])
                    messages.success(request, "Foto guardada.")
=======
            FotoReferencia.objects.create(
                cliente=c, archivo=request.FILES["foto"], descripcion=request.POST.get("descripcion", "")[:120]
            )
            messages.success(request, "Foto guardada.")
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
        else:
            for campo in ("nombre", "email", "pref_maquina", "pref_estilo", "pref_barba"):
                if campo in request.POST:
                    setattr(c, campo, request.POST[campo].strip()[:120])
<<<<<<< HEAD
            bp = request.POST.get("barbero_preferido")
            c.barbero_preferido = Barbero.objects.filter(pk=bp).first() if bp else None
            c.save()
            messages.success(request, "Datos actualizados. Tu barbero verá tus preferencias antes de tu cita.")
        return redirect("cliente:perfil")
    return render(request, "cliente/perfil.html", {
        "cliente": c, "barberos": Barbero.objects.filter(activo=True), "nav": "perfil",
        "texto_marketing": priv.texto_marketing(), "texto_sensibles": priv.texto_sensibles(),
        "consentimientos": c.consentimientos.all()[:10],
    })


@require_POST
@_requiere_cliente
def autorizaciones(request):
    """Otorgar o revocar autorizaciones opcionales en cualquier momento (Ley 1581 art. 8 lit. e)."""
    c = request.cliente
    cambios = []
    for campo, tipo in (("acepta_marketing", Consentimiento.MARKETING), ("acepta_sensibles", Consentimiento.SENSIBLES),
                        ("acepta_whatsapp", Consentimiento.MENSAJES_SERVICIO)):
        nuevo = bool(request.POST.get(campo))
        if nuevo != getattr(c, campo):
            setattr(c, campo, nuevo)
            priv.registrar_consentimiento(c, tipo, nuevo, request)
            cambios.append(tipo)
    c.save(update_fields=["acepta_marketing", "acepta_sensibles", "acepta_whatsapp"])
    if Consentimiento.SENSIBLES in cambios and not c.acepta_sensibles:
        priv.borrar_fotos(c)
        messages.success(request, "Revocaste la autorización de fotografías y las borramos.")
    elif cambios:
        messages.success(request, "Autorizaciones actualizadas.")
    if not c.acepta_whatsapp:
        messages.info(request, "No recibirás confirmaciones ni recordatorios por WhatsApp; revisa tus citas en «Mis citas».")
    return redirect(reverse("cliente:perfil") + "#mis-datos")


@_requiere_cliente
def descargar_datos(request):
    """Acceso del titular a toda su información (Ley 1581 art. 8 lit. a y art. 14)."""
    import json
    datos = priv.exportar_datos(request.cliente)
    resp = HttpResponse(json.dumps(datos, ensure_ascii=False, indent=2), content_type="application/json; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="mis-datos-{timezone.localdate():%Y%m%d}.json"'
    resp["Cache-Control"] = "no-store"
    return resp


@require_POST
@_requiere_cliente
def eliminar_cuenta(request):
    """Supresión inmediata a solicitud del titular (Ley 1581 art. 8 lit. e)."""
    if request.POST.get("confirmacion", "").strip().upper() != "ELIMINAR":
        messages.error(request, "Escribe ELIMINAR para confirmar.")
        return redirect(reverse("cliente:perfil") + "#mis-datos")
    c = request.cliente
    priv.registrar_consentimiento(c, Consentimiento.TRATAMIENTO, False, request)
    priv.anonimizar_cliente(c, "El titular eliminó su cuenta desde Mis datos")
    request.session.flush()
    messages.success(request, "Eliminamos tu cuenta y tus datos personales. Conservamos solo los soportes contables sin datos que te identifiquen.")
    return redirect("cliente:inicio")


@_requiere_cliente
def reaceptar_politica(request):
    c = request.cliente
    siguiente = request.GET.get("next") or request.POST.get("next") or reverse("cliente:perfil")
    if not siguiente.startswith("/"):
        siguiente = reverse("cliente:perfil")
    if request.method == "POST":
        if request.POST.get("acepta_datos") and request.POST.get("acepta_terminos"):
            priv.aplicar_autorizaciones(c, sensibles=c.acepta_sensibles, marketing=c.acepta_marketing,
                                        mensajes_servicio=c.acepta_whatsapp, request=request)
            return redirect(siguiente)
        messages.error(request, "Para seguir usando tu cuenta debes aceptar la nueva versión. Si no estás de acuerdo, puedes eliminar tu cuenta.")
    return render(request, "cliente/reaceptar.html", {"cliente": c, "next": siguiente, "nav": "perfil",
                                                       "texto_autorizacion": priv.texto_autorizacion()})


@_requiere_cliente
def borrar_foto(request, pk):
    if request.method == "POST":
        for f in FotoReferencia.objects.filter(pk=pk, cliente=request.cliente):
            f.archivo.delete(save=False)
            f.delete()
=======
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
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
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

"""Páginas legales, ejercicio de derechos (habeas data), baja de publicidad y archivos privados."""
import re

from django.conf import settings
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from . import privacidad as priv
from .archivos import servir, validar_archivo
from .models import Cliente, Consentimiento, FotoReferencia, SolicitudDatos
from .otp import normalizar_telefono
from .roles import rol_de, BARBERO


TIPOS_DOC = [("CC", "Cédula de ciudadanía"), ("CE", "Cédula de extranjería"), ("PA", "Pasaporte"),
             ("PPT", "Permiso por protección temporal")]


def _ctx(request, doc, **extra):
    return {"doc": doc, "nav": "perfil", "encargados": settings.ENCARGADOS,
            "faltantes": priv.faltantes_responsable(), **extra}


def privacidad(request):
    return render(request, "legal/privacidad.html", _ctx(request, "privacidad"))


def terminos(request):
    return render(request, "legal/terminos.html", _ctx(request, "terminos"))


def cookies(request):
    return render(request, "legal/cookies.html", _ctx(request, "cookies"))


def derechos(request):
    from .views_cliente import cliente_actual
    cliente = cliente_actual(request)
    datos = {"calidad": "titular", "tipo_documento": "CC"}
    if cliente:
        datos.update(nombre=cliente.nombre, telefono=cliente.telefono, email=cliente.email)
    errores = {}
    if request.method == "POST":
        lim = settings.LIMITES["DERECHOS_POR_IP_DIA"]
        if priv.limite_excedido(f"derechos:{priv.ip_de(request)}", lim, 86400):
            errores["general"] = "Recibimos demasiadas solicitudes desde tu conexión. Escríbenos al correo indicado."
        campos = ("tipo", "calidad", "nombre", "tipo_documento", "documento", "telefono", "email", "direccion",
                  "descripcion")
        datos = {k: request.POST.get(k, "").strip() for k in campos}
        datos["acepta"] = bool(request.POST.get("acepta"))
        if datos["tipo"] not in dict(SolicitudDatos.TIPOS):
            errores["tipo"] = "Elige qué quieres hacer."
        if datos["calidad"] not in dict(SolicitudDatos.CALIDADES):
            datos["calidad"] = "titular"
        if datos["tipo_documento"] not in dict(TIPOS_DOC):
            datos["tipo_documento"] = "CC"
        if len(datos["nombre"]) < 3:
            errores["nombre"] = "Escribe el nombre completo."
        if not re.fullmatch(r"[A-Za-z0-9.\- ]{4,20}", datos["documento"]):
            errores["documento"] = "Escribe un número de documento válido."
        tel = normalizar_telefono(datos["telefono"])
        if not tel:
            errores["telefono"] = "Escribe un celular válido."
        try:
            validate_email(datos["email"])
        except ValidationError:
            errores["email"] = "Escribe un correo válido."
        if len(datos["descripcion"]) < 10:
            errores["descripcion"] = "Cuéntanos un poco más (mínimo 10 caracteres)."
        adjunto = request.FILES.get("adjunto")
        err = validar_archivo(adjunto, permitir_pdf=True)
        if err:
            errores["adjunto"] = err
        if datos["calidad"] != "titular" and not adjunto:
            errores["adjunto"] = "Adjunta el documento que acredita tu calidad de causahabiente o representante."
        if not datos["acepta"]:
            errores["acepta"] = "Necesitamos esta autorización para poder tramitar tu solicitud."
        if not errores:
            titular = Cliente.objects.filter(telefono=tel, anonimizado_en__isnull=True).first()
            verificada = bool(cliente and titular and cliente.pk == titular.pk and datos["calidad"] == "titular")
            s = priv.radicar_solicitud(
                tipo=datos["tipo"], request=request, cliente=titular, calidad=datos["calidad"],
                nombre=datos["nombre"][:120], tipo_documento=datos["tipo_documento"], documento=datos["documento"],
                telefono=tel, email=datos["email"], direccion=datos["direccion"][:160],
                descripcion=datos["descripcion"][:3000], identidad_verificada=verificada,
            )
            if adjunto:
                s.adjunto = adjunto
                s.save(update_fields=["adjunto"])
            request.session["ultima_solicitud"] = s.pk
            return redirect("legal:derechos_ok")
    return render(request, "legal/derechos.html", _ctx(
        request, "derechos", tipos=SolicitudDatos.TIPOS, calidades=SolicitudDatos.CALIDADES, datos=datos,
        errores=errores, cliente=cliente, tipos_doc=TIPOS_DOC))


def derechos_ok(request):
    pk = request.session.get("ultima_solicitud")
    if not pk:
        return redirect("legal:derechos")
    s = get_object_or_404(SolicitudDatos, pk=pk)
    return render(request, "legal/derechos_ok.html", _ctx(request, "derechos", s=s))


def baja(request, token):
    """Enlace para cancelar publicidad en cualquier momento (Ley 2300 de 2023, art. 5 par. 2)."""
    cliente = get_object_or_404(Cliente, token_baja=token)
    hecho = not cliente.acepta_marketing
    if request.method == "POST" and cliente.acepta_marketing:
        cliente.acepta_marketing = False
        cliente.save(update_fields=["acepta_marketing"])
        priv.registrar_consentimiento(cliente, Consentimiento.MARKETING, False, request, canal="whatsapp")
        hecho = True
    return render(request, "legal/baja.html", {"hecho": hecho, "nav": "inicio"})


# ---------------- Archivos privados ----------------
def foto(request, pk):
    """La foto solo la ve su titular (sesión) o el equipo con permiso sobre ese cliente."""
    from .views_cliente import cliente_actual
    f = get_object_or_404(FotoReferencia.objects.select_related("cliente"), pk=pk)
    c = cliente_actual(request)
    if c and c.pk == f.cliente_id:
        return servir(f.archivo)
    if request.user.is_authenticated:
        rol = rol_de(request.user)
        if rol is None:
            return HttpResponseForbidden()
        if rol == BARBERO and not f.cliente.citas.filter(barbero=request.user.barbero).exists():
            return HttpResponseForbidden()
        priv.auditar(request, "ver_foto", f.cliente, f"foto {f.pk}")
        return servir(f.archivo)
    raise Http404


def adjunto_solicitud(request, pk):
    if not request.user.is_authenticated or rol_de(request.user) != "admin":
        raise Http404
    s = get_object_or_404(SolicitudDatos, pk=pk)
    priv.auditar(request, "ver_adjunto_solicitud", s.cliente, s.radicado)
    return servir(s.adjunto)

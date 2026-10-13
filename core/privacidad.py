"""Cumplimiento de protección de datos personales en Colombia.

Marco: Ley 1581 de 2012, Decreto 1074 de 2015 (cap. 25 y 26; antes Decreto 1377 de 2013),
Ley 2300 de 2023 (mensajes publicitarios) y Ley 1480 de 2011 (Estatuto del Consumidor).

Este módulo concentra:
- los textos exactos de autorización (lo que se muestra es lo que se guarda como prueba),
- el registro de consentimientos y revocatorias,
- la supresión o anonimización y la exportación de datos del titular,
- la radicación de consultas y reclamos con plazos en días hábiles,
- las reglas de horario y frecuencia para publicidad,
- los límites de intentos y la bitácora de accesos.
"""
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .festivos import es_festivo, sumar_dias_habiles
from .models import (Cita, Cliente, Consentimiento, FotoReferencia, MensajeEnviado, RegistroAcceso,
                     SolicitudDatos)

R = settings.RESPONSABLE


def nombre_responsable():
    return R["RAZON_SOCIAL"] or settings.BARBERIA["NOMBRE"]


# --------------------------------------------------------------------------------------------
# Textos de autorización (Ley 1581 art. 9 y 12; Decreto 1074 art. 2.2.2.25.2.2 y 2.2.2.25.2.3)
# --------------------------------------------------------------------------------------------
def texto_autorizacion():
    return (
        f"Autorizo de manera previa, expresa e informada a {nombre_responsable()} "
        f"({R['TIPO_ID']} {R['NUMERO_ID'] or 'pendiente'}) para recolectar, almacenar, usar y suprimir mis datos "
        "personales (nombre, celular, correo, historial de citas, preferencias de corte y pagos) con el fin de "
        "gestionar mis reservas, enviarme la confirmación y los recordatorios de mis citas, prestarme el servicio, "
        "administrar el programa de puntos, atender mis solicitudes y cumplir obligaciones legales y contables, "
        "conforme a la Política de Tratamiento de Datos Personales versión "
        f"{settings.POLITICA_VERSION}. Declaro que soy mayor de 18 años. Sé que puedo conocer, actualizar, "
        "rectificar y suprimir mis datos y revocar esta autorización "
        + (f"escribiendo a {R['EMAIL_DATOS']}" if R["EMAIL_DATOS"] else "por los canales indicados en la política")
        + " o desde la sección «Mis datos»."
    )


def texto_sensibles():
    return (
        "Autorizo de forma expresa y facultativa el tratamiento de las fotografías que suba o que el equipo "
        "tome de mi corte (dato sensible por tratarse de mi imagen) con el único fin de guardar mi referencia "
        "de estilo y mi historial de cortes. Sé que no estoy obligado a autorizarlo y que no es condición "
        "para recibir el servicio. Las fotos no se publicarán sin una autorización adicional."
    )


def texto_marketing():
    return (
        "Acepto recibir promociones, novedades y recordatorios para volver por WhatsApp, SMS o correo. "
        "Es opcional, no es condición para reservar y puedo darme de baja en cualquier momento. Se enviarán "
        "solo de lunes a viernes de 7:00 a. m. a 7:00 p. m. y sábados de 8:00 a. m. a 3:00 p. m., "
        "nunca domingos ni festivos (Ley 2300 de 2023)."
    )


def texto_mensajes_servicio():
    return ("Acepto recibir por WhatsApp los mensajes necesarios del servicio: código de verificación, "
            "confirmación, recordatorios y cambios de mis citas.")


def texto_terminos():
    return f"Acepto los Términos y Condiciones del servicio versión {settings.TERMINOS_VERSION}."


TEXTOS = {
    Consentimiento.TRATAMIENTO: texto_autorizacion,
    Consentimiento.SENSIBLES: texto_sensibles,
    Consentimiento.MARKETING: texto_marketing,
    Consentimiento.MENSAJES_SERVICIO: texto_mensajes_servicio,
    Consentimiento.TERMINOS: texto_terminos,
}


def ip_de(request):
    if request is None:
        return None
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR")) or None


def registrar_consentimiento(cliente, tipo, otorgado, request=None, canal="web", usuario=None, telefono=None):
    version = settings.TERMINOS_VERSION if tipo == Consentimiento.TERMINOS else settings.POLITICA_VERSION
    return Consentimiento.objects.create(
        cliente=cliente, telefono=telefono or (cliente.telefono if cliente else ""), tipo=tipo, otorgado=otorgado,
        version=version, texto=TEXTOS[tipo](), canal=canal, ip=ip_de(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
        registrado_por=usuario,
    )


@transaction.atomic
def aplicar_autorizaciones(cliente, *, sensibles, marketing, mensajes_servicio=True, request=None, canal="web",
                           usuario=None):
    """Registra la autorización principal + las opcionales y actualiza las banderas del cliente."""
    registrar_consentimiento(cliente, Consentimiento.TRATAMIENTO, True, request, canal, usuario)
    registrar_consentimiento(cliente, Consentimiento.TERMINOS, True, request, canal, usuario)
    registrar_consentimiento(cliente, Consentimiento.MENSAJES_SERVICIO, mensajes_servicio, request, canal, usuario)
    if sensibles != cliente.acepta_sensibles or sensibles:
        registrar_consentimiento(cliente, Consentimiento.SENSIBLES, sensibles, request, canal, usuario)
    if marketing != cliente.acepta_marketing or marketing:
        registrar_consentimiento(cliente, Consentimiento.MARKETING, marketing, request, canal, usuario)
    cliente.acepta_sensibles = sensibles
    cliente.acepta_marketing = marketing
    cliente.acepta_whatsapp = mensajes_servicio
    cliente.politica_version = settings.POLITICA_VERSION
    cliente.autorizado_en = timezone.now()
    cliente.save(update_fields=["acepta_sensibles", "acepta_marketing", "acepta_whatsapp", "politica_version",
                                "autorizado_en"])
    if not sensibles:
        borrar_fotos(cliente)


def borrar_fotos(cliente):
    for f in cliente.fotos.all():
        f.archivo.delete(save=False)
        f.delete()


# --------------------------------------------------------------------------------------------
# Derechos del titular: acceso (exportar) y supresión (anonimizar)
# --------------------------------------------------------------------------------------------
def exportar_datos(cliente):
    """Toda la información del registro individual del titular (Ley 1581 art. 14)."""
    loc = timezone.localtime
    return {
        "responsable": {"nombre": nombre_responsable(), "identificacion": f"{R['TIPO_ID']} {R['NUMERO_ID']}",
                        "contacto_datos": R["EMAIL_DATOS"], "politica_version": settings.POLITICA_VERSION},
        "generado_en": loc(timezone.now()).isoformat(),
        "datos_personales": {
            "nombre": cliente.nombre, "telefono": cliente.telefono, "email": cliente.email,
            "fecha_nacimiento": cliente.fecha_nacimiento.isoformat() if cliente.fecha_nacimiento else None,
            "barbero_preferido": cliente.barbero_preferido.nombre if cliente.barbero_preferido else None,
            "preferencias": {"maquina": cliente.pref_maquina, "estilo": cliente.pref_estilo, "barba": cliente.pref_barba},
            "notas_del_equipo": cliente.notas,
            "puntos": cliente.puntos, "no_shows": cliente.no_shows,
            "cliente_desde": loc(cliente.creado).isoformat(),
            "ultima_visita": loc(cliente.ultima_visita).isoformat() if cliente.ultima_visita else None,
        },
        "autorizaciones_vigentes": {
            "tratamiento_version": cliente.politica_version, "mensajes_servicio": cliente.acepta_whatsapp,
            "publicidad": cliente.acepta_marketing, "fotografias": cliente.acepta_sensibles,
        },
        "historial_autorizaciones": [
            {"fecha": loc(c.fecha).isoformat(), "tipo": c.get_tipo_display(), "otorgado": c.otorgado,
             "version": c.version, "canal": c.get_canal_display(), "texto": c.texto}
            for c in cliente.consentimientos.all()
        ],
        "citas": [
            {"inicio": loc(c.inicio).isoformat(), "servicios": c.nombres_servicios, "barbero": c.barbero.nombre,
             "estado": c.get_estado_display(), "valor_cop": c.precio_total, "nota": c.notas_cliente}
            for c in cliente.citas.select_related("barbero").prefetch_related("servicios")
        ],
        "fotografias": [{"fecha": loc(f.creado).isoformat(), "descripcion": f.descripcion,
                         "tipo": "resultado" if f.es_resultado else "referencia"} for f in cliente.fotos.all()],
        "mensajes_recibidos": [{"fecha": loc(m.enviado).isoformat(), "tipo": m.get_tipo_display(), "canal": m.canal}
                               for m in MensajeEnviado.objects.filter(cliente=cliente)],
        "solicitudes": [{"radicado": s.radicado, "tipo": s.get_tipo_display(), "estado": s.get_estado_display()}
                        for s in cliente.solicitudes.all()],
    }


@transaction.atomic
def anonimizar_cliente(cliente, motivo="Solicitud del titular", usuario=None):
    """Supresión de datos personales.

    Se borran los datos que identifican al titular y sus fotos. Las citas y pagos se conservan sin datos
    personales porque son soportes contables que la ley obliga a guardar (Código de Comercio art. 60 y
    Estatuto Tributario): la supresión no procede sobre lo que hay deber legal de conservar
    (Ley 1581 art. 8 lit. e; Decreto 1074 arts. 2.2.2.25.2.6 y 2.2.2.25.2.8).
    Las autorizaciones registradas se conservan como prueba, con el teléfono, por el término legal.
    """
    ahora = timezone.now()
    for cita in cliente.citas.filter(inicio__gt=ahora, estado__in=[Cita.PENDIENTE, Cita.CONFIRMADA]):
        cita.estado = Cita.CANCELADA
        cita.save(update_fields=["estado"])
    cliente.citas.update(notas_cliente="")
    borrar_fotos(cliente)
    MensajeEnviado.objects.filter(cliente=cliente).update(contenido="[suprimido]", telefono="")
    cliente.nombre = "Titular suprimido"
    cliente.telefono = f"anon-{secrets.token_hex(6)}"
    cliente.email = ""
    cliente.fecha_nacimiento = None
    cliente.pref_maquina = cliente.pref_estilo = cliente.pref_barba = cliente.notas = ""
    cliente.barbero_preferido = None
    cliente.acepta_whatsapp = cliente.acepta_marketing = cliente.acepta_sensibles = False
    cliente.puntos = 0
    cliente.anonimizado_en = ahora
    cliente.save()
    RegistroAcceso.objects.create(usuario=usuario, accion="supresion", cliente=cliente, detalle=motivo[:240])
    return cliente


# --------------------------------------------------------------------------------------------
# Consultas y reclamos (Ley 1581 arts. 14 y 15)
# --------------------------------------------------------------------------------------------
PLAZOS = {"consulta": (10, 5), "reclamo": (15, 8)}  # (días hábiles, prórroga máxima)


def plazo_para(tipo):
    return PLAZOS["consulta" if tipo == SolicitudDatos.CONSULTA else "reclamo"]


def nuevo_radicado():
    hoy = timezone.localdate()
    while True:
        r = f"HD-{hoy:%Y%m%d}-{secrets.randbelow(10**4):04d}"
        if not SolicitudDatos.objects.filter(radicado=r).exists():
            return r


def radicar_solicitud(*, tipo, request=None, cliente=None, **datos):
    dias, _ = plazo_para(tipo)
    hoy = timezone.localdate()
    estado = SolicitudDatos.EN_TRAMITE if tipo in SolicitudDatos.RECLAMOS else SolicitudDatos.RECIBIDA
    s = SolicitudDatos.objects.create(
        radicado=nuevo_radicado(), tipo=tipo, cliente=cliente, estado=estado,
        vence_en=sumar_dias_habiles(hoy, dias), ip=ip_de(request), **datos,
    )
    return s


def prorrogar(solicitud, motivo):
    _, extra = plazo_para(solicitud.tipo)
    solicitud.prorroga_hasta = sumar_dias_habiles(solicitud.vence_en, extra)
    solicitud.motivo_prorroga = motivo[:240]
    solicitud.estado = SolicitudDatos.PRORROGADA
    solicitud.save(update_fields=["prorroga_hasta", "motivo_prorroga", "estado"])
    return solicitud


# --------------------------------------------------------------------------------------------
# Publicidad (Ley 2300 de 2023, arts. 3 y 5)
# --------------------------------------------------------------------------------------------
def en_horario_publicidad(momento=None):
    momento = timezone.localtime(momento or timezone.now())
    d = momento.date()
    if d.weekday() == 6 or es_festivo(d):
        return False
    h = settings.HORARIO_PUBLICIDAD
    ini, fin = h["SABADO"] if d.weekday() == 5 else h["LUNES_VIERNES"]
    minutos = momento.hour * 60 + momento.minute
    return ini * 60 <= minutos < fin * 60


def puede_recibir_publicidad(cliente, momento=None):
    """(bool, motivo)"""
    if not cliente.acepta_marketing or cliente.anonimizado_en:
        return False, "sin autorización para publicidad"
    if not en_horario_publicidad(momento):
        return False, "fuera del horario permitido por la Ley 2300 de 2023"
    dias = settings.HORARIO_PUBLICIDAD["DIAS_ENTRE_MENSAJES"]
    reciente = MensajeEnviado.objects.filter(
        cliente=cliente, tipo="reactivacion", enviado__gte=(momento or timezone.now()) - timedelta(days=dias)
    ).exists()
    if reciente:
        return False, f"ya recibió un mensaje publicitario en los últimos {dias} días"
    return True, ""


# --------------------------------------------------------------------------------------------
# Límites de intentos y bitácora
# --------------------------------------------------------------------------------------------
def limite_excedido(clave, maximo, ventana_seg):
    """Cuenta un intento y devuelve True si se superó el máximo en la ventana."""
    k = f"lim:{clave}"
    if cache.add(k, 1, ventana_seg):
        return False
    try:
        n = cache.incr(k)
    except ValueError:
        cache.set(k, 1, ventana_seg)
        n = 1
    return n > maximo


def auditar(request, accion, cliente=None, detalle=""):
    RegistroAcceso.objects.create(
        usuario=request.user if request.user.is_authenticated else None, accion=accion, cliente=cliente,
        detalle=detalle[:240], ip=ip_de(request),
    )


def faltantes_responsable():
    """Campos obligatorios del responsable que siguen vacíos (art. 2.2.2.25.3.1 num. 1)."""
    nombres = {"RAZON_SOCIAL": "razón social o nombre", "NUMERO_ID": "NIT o cédula", "DIRECCION": "dirección",
               "EMAIL_DATOS": "correo para datos personales", "TELEFONO": "teléfono"}
    return [v for k, v in nombres.items() if not R.get(k)]

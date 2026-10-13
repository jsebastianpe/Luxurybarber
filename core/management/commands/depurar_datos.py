"""Aplica los plazos de conservación de la política (principio de temporalidad, Decreto 1074 art. 2.2.2.25.2.8).

Prográmalo una vez al día:  python manage.py depurar_datos
Usa --simular para ver qué haría sin cambiar nada.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db.models import Max, Q
from django.utils import timezone

from core.models import (Cita, Cliente, CodigoVerificacion, MensajeEnviado, RegistroAcceso, RetencionCupo,
                         SolicitudDatos)
from core.privacidad import anonimizar_cliente, borrar_fotos


class Command(BaseCommand):
    help = "Borra o anonimiza los datos que superaron su plazo de conservación"

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true")

    def handle(self, *args, simular=False, **opts):
        R = settings.RETENCION
        ahora = timezone.now()
        hace = lambda dias: ahora - timedelta(days=dias)  # noqa: E731
        res = {}

        def borrar(nombre, qs):
            res[nombre] = qs.count()
            if not simular:
                qs.delete()

        borrar("codigos_otp", CodigoVerificacion.objects.filter(creado__lt=hace(R["CODIGOS_OTP"])))
        borrar("retenciones_vencidas", RetencionCupo.objects.filter(expira__lt=ahora))
        borrar("bitacora_accesos", RegistroAcceso.objects.filter(fecha__lt=hace(R["AUDITORIA"])))
        borrar("solicitudes_cerradas", SolicitudDatos.objects.filter(
            recibida_en__lt=hace(R["SOLICITUDES"]), estado__in=[SolicitudDatos.RESUELTA, SolicitudDatos.DESISTIDA]))
        viejos = MensajeEnviado.objects.filter(enviado__lt=hace(R["MENSAJES"]))
        res["mensajes"] = viejos.count()
        if not simular:
            viejos.update(contenido="[depurado]", telefono="")
        res["sesiones"] = Session.objects.filter(expire_date__lt=ahora).count()
        if not simular:
            Session.objects.filter(expire_date__lt=ahora).delete()

        # Reclamos incompletos: desistimiento a los 2 meses del requerimiento (Ley 1581 art. 15)
        desistidas = SolicitudDatos.objects.filter(estado=SolicitudDatos.INCOMPLETA,
                                                   requerida_en__lt=timezone.localdate() - timedelta(days=61))
        res["solicitudes_desistidas"] = desistidas.count()
        if not simular:
            desistidas.update(estado=SolicitudDatos.DESISTIDA)

        activos = Cliente.objects.filter(anonimizado_en__isnull=True).annotate(ultima_cita=Max("citas__inicio"))
        # Fotos de clientes sin visitas en el plazo
        sin_fotos = activos.filter(fotos__isnull=False).filter(
            Q(ultima_visita__lt=hace(R["FOTOS_INACTIVO"])) | Q(ultima_visita__isnull=True, creado__lt=hace(R["FOTOS_INACTIVO"]))
        ).distinct()
        res["clientes_fotos_borradas"] = sin_fotos.count()
        if not simular:
            for c in sin_fotos:
                borrar_fotos(c)

        # Clientes sin actividad: se anonimizan (sin reclamo abierto)
        inactivos = activos.filter(
            Q(ultima_cita__lt=hace(R["CLIENTE_INACTIVO"])) | Q(ultima_cita__isnull=True, creado__lt=hace(R["CLIENTE_INACTIVO"]))
        ).exclude(solicitudes__estado__in=SolicitudDatos.ABIERTAS)
        res["clientes_anonimizados"] = inactivos.count()
        if not simular:
            for c in inactivos:
                anonimizar_cliente(c, "Plazo de conservación cumplido")

        for k, v in res.items():
            self.stdout.write(f"{'[simulación] ' if simular else ''}{k}: {v}")
        self.stdout.write(self.style.SUCCESS("Depuración terminada."))

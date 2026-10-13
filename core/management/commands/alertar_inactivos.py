"""Envía un mensaje de reactivación a clientes que llevan N días sin venir (una vez por umbral).

Uso:  python manage.py alertar_inactivos --dias 45
Prográmalo una vez al día (por ejemplo a las 10:00 a. m.).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core import notificaciones
from core.models import Cita, Cliente, MensajeEnviado


class Command(BaseCommand):
    help = "Mensaje automático a clientes inactivos"

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=45)
        parser.add_argument("--simular", action="store_true", help="Solo lista, no envía")

    def handle(self, *args, dias, simular, **opts):
        ahora = timezone.now()
        limite = ahora - timedelta(days=dias)
        candidatos = (Cliente.objects.filter(ultima_visita__lt=limite, acepta_whatsapp=True)
                      .exclude(citas__inicio__gte=ahora, citas__estado__in=[Cita.PENDIENTE, Cita.CONFIRMADA])
                      .distinct())
        enviados = 0
        for c in candidatos:
            # No repetir si ya se le escribió después de su última visita
            if MensajeEnviado.objects.filter(cliente=c, tipo="reactivacion", enviado__gt=c.ultima_visita).exists():
                continue
            if simular:
                self.stdout.write(f"- {c.nombre} ({c.dias_inactivo} días)")
            else:
                notificaciones.reactivacion(c)
            enviados += 1
        self.stdout.write(self.style.SUCCESS(f"{'Se enviarían' if simular else 'Enviados'}: {enviados}"))

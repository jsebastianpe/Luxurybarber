"""Envía recordatorios 24 h y 2 h antes de cada cita y limpia retenciones vencidas.

Prográmalo cada 10–15 minutos:
  - Linux/macOS (cron):   */15 * * * * cd /ruta/barberia && .venv/bin/python manage.py enviar_recordatorios
  - Windows: Programador de tareas con el mismo comando
  - O con Celery beat / Django-Q2 si ya usas un worker (ver README)
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core import notificaciones
from core.models import Cita, RetencionCupo


class Command(BaseCommand):
    help = "Envía recordatorios de citas por WhatsApp (24 h y 2 h antes)"

    def handle(self, *args, **opts):
        ahora = timezone.now()
        base = Cita.objects.filter(
            estado__in=[Cita.PENDIENTE, Cita.CONFIRMADA], cliente__acepta_whatsapp=True
        ).select_related("cliente", "barbero")

        n24 = 0
        for cita in base.filter(recordatorio_24h=False, inicio__gt=ahora + timedelta(hours=3),
                                inicio__lte=ahora + timedelta(hours=24)):
            notificaciones.recordatorio(cita, "recordatorio_24h")
            cita.recordatorio_24h = True
            cita.save(update_fields=["recordatorio_24h"])
            n24 += 1

        n2 = 0
        for cita in base.filter(recordatorio_2h=False, inicio__gt=ahora, inicio__lte=ahora + timedelta(hours=2)):
            notificaciones.recordatorio(cita, "recordatorio_2h")
            cita.recordatorio_2h = True
            cita.save(update_fields=["recordatorio_2h"])
            n2 += 1

        borradas, _ = RetencionCupo.objects.filter(expira__lte=ahora).delete()
        self.stdout.write(self.style.SUCCESS(f"Recordatorios: {n24} de 24 h, {n2} de 2 h. Retenciones vencidas borradas: {borradas}."))

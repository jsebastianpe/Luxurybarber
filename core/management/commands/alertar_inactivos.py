<<<<<<< HEAD
"""Mensaje publicitario de reactivación a clientes inactivos que AUTORIZARON publicidad.

Respeta la Ley 2300 de 2023: solo en horario permitido (L-V 7:00-19:00, sáb 8:00-15:00, nunca domingos
ni festivos), máximo un mensaje por semana y con enlace para darse de baja.

Uso:  python manage.py alertar_inactivos --dias 45 [--simular]
Prográmalo una vez al día en horario permitido (por ejemplo, a las 10:00 a. m.).
=======
"""Envía un mensaje de reactivación a clientes que llevan N días sin venir (una vez por umbral).

Uso:  python manage.py alertar_inactivos --dias 45
Prográmalo una vez al día (por ejemplo a las 10:00 a. m.).
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core import notificaciones
from core.models import Cita, Cliente, MensajeEnviado
<<<<<<< HEAD
from core.privacidad import en_horario_publicidad, puede_recibir_publicidad


class Command(BaseCommand):
    help = "Mensaje automático a clientes inactivos (con autorización de publicidad)"
=======


class Command(BaseCommand):
    help = "Mensaje automático a clientes inactivos"
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=45)
        parser.add_argument("--simular", action="store_true", help="Solo lista, no envía")

    def handle(self, *args, dias, simular, **opts):
<<<<<<< HEAD
        if not simular and not en_horario_publicidad():
            self.stdout.write(self.style.WARNING("Fuera del horario permitido por la Ley 2300 de 2023. No se envió nada."))
            return
        ahora = timezone.now()
        candidatos = (Cliente.objects.filter(ultima_visita__lt=ahora - timedelta(days=dias), acepta_marketing=True,
                                             anonimizado_en__isnull=True)
=======
        ahora = timezone.now()
        limite = ahora - timedelta(days=dias)
        candidatos = (Cliente.objects.filter(ultima_visita__lt=limite, acepta_whatsapp=True)
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
                      .exclude(citas__inicio__gte=ahora, citas__estado__in=[Cita.PENDIENTE, Cita.CONFIRMADA])
                      .distinct())
        enviados = 0
        for c in candidatos:
<<<<<<< HEAD
            if MensajeEnviado.objects.filter(cliente=c, tipo="reactivacion", enviado__gt=c.ultima_visita).exists():
                continue  # ya se le escribió después de su última visita
            ok, motivo = puede_recibir_publicidad(c) if not simular else (True, "")
            if not ok:
=======
            # No repetir si ya se le escribió después de su última visita
            if MensajeEnviado.objects.filter(cliente=c, tipo="reactivacion", enviado__gt=c.ultima_visita).exists():
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
                continue
            if simular:
                self.stdout.write(f"- {c.nombre} ({c.dias_inactivo} días)")
            else:
                notificaciones.reactivacion(c)
            enviados += 1
        self.stdout.write(self.style.SUCCESS(f"{'Se enviarían' if simular else 'Enviados'}: {enviados}"))

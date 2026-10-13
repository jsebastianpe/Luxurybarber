"""Configura y prueba la integración con WhatsApp Cloud API.

  python manage.py whatsapp --verificar             Comprueba token, número emisor y plantillas
  python manage.py whatsapp --crear-plantilla-otp   Crea la plantilla de autenticación (botón «Copiar código»)
  python manage.py whatsapp --probar 3001234567     Envía un código de prueba (no sirve para iniciar sesión)
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import whatsapp as wa
from core.otp import _generar_codigo, normalizar_telefono, pais_permitido


class Command(BaseCommand):
    help = "Configura y prueba WhatsApp Cloud API"

    def add_arguments(self, parser):
        parser.add_argument("--verificar", action="store_true")
        parser.add_argument("--crear-plantilla-otp", action="store_true")
        parser.add_argument("--probar", metavar="CELULAR")

    def handle(self, *args, **o):
        w = settings.WHATSAPP
        if not wa.configurado():
            raise CommandError("Faltan WHATSAPP_TOKEN y/o WHATSAPP_PHONE_ID en .env")
        if o["verificar"]:
            try:
                info = wa.info_numero()
            except wa.WhatsAppError as e:
                raise CommandError(f"No se pudo validar el número: {e}")
            self.stdout.write(self.style.SUCCESS(
                f"Número emisor: {info.get('display_phone_number')} · {info.get('verified_name')} · "
                f"calidad {info.get('quality_rating')}"))
            if w["WABA_ID"]:
                for t in wa.plantillas():
                    marca = "←" if t.get("name") in {w["PLANTILLA_OTP"], w["PLANTILLA_CONFIRMACION"],
                                                     w["PLANTILLA_RECORDATORIO"], w["PLANTILLA_CANCELACION"],
                                                     w["PLANTILLA_PROMOCION"]} else ""
                    self.stdout.write(f"  {t.get('name')} [{t.get('language')}] {t.get('category')} {t.get('status')} {marca}")
            faltan = [n for n, v in (("WHATSAPP_APP_SECRET", w["APP_SECRET"]), ("WHATSAPP_VERIFY_TOKEN", w["VERIFY_TOKEN"])) if not v]
            if faltan:
                self.stdout.write(self.style.WARNING(f"Sin {', '.join(faltan)}: el webhook de estados de entrega está desactivado."))
        if o["crear_plantilla_otp"]:
            try:
                r = wa.crear_plantilla_otp()
            except wa.WhatsAppError as e:
                raise CommandError(f"Meta rechazó la plantilla: {e}")
            self.stdout.write(self.style.SUCCESS(f"Plantilla '{w['PLANTILLA_OTP']}' enviada a revisión: {r}"))
        if o["probar"]:
            tel = normalizar_telefono(o["probar"])
            if not tel or not pais_permitido(tel):
                raise CommandError("Celular inválido o país no permitido (WHATSAPP_PAISES_OTP)")
            try:
                res = wa.enviar_otp(tel, _generar_codigo())
            except wa.WhatsAppError as e:
                raise CommandError(f"Falló el envío: {e} → {e.para_usuario}")
            self.stdout.write(self.style.SUCCESS(f"Enviado a {wa.enmascarar(tel)} · wamid {res.wamid}. "
                                                 "Revisa el estado en el webhook (entregado/leído)."))

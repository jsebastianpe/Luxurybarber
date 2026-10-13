"""Pruebas de las reglas críticas: disponibilidad, doble reserva, flujo de reserva, caja y comisiones.

Ejecuta:  python manage.py test
"""
from datetime import datetime, time, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone

from core import disponibilidad as disp
from core import operaciones as ops
from core.models import (Barbero, Bloqueo, Caja, Cita, Cliente, CodigoVerificacion, HorarioLaboral,
                         MovimientoInventario, Producto, Servicio)
from core.otp import normalizar_telefono


def manana():
    return timezone.localdate() + timedelta(days=1)


def en(d, h, m=0):
    return timezone.make_aware(datetime.combine(d, time(h, m)))


<<<<<<< HEAD
CODIGO = "482915"


class Base(TestCase):
    def setUp(self):
        from unittest import mock
        from django.core.cache import cache
        cache.clear()
        p = mock.patch("core.otp._generar_codigo", return_value=CODIGO)
        p.start()
        self.addCleanup(p.stop)
=======
class Base(TestCase):
    def setUp(self):
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
        self.corte = Servicio.objects.create(nombre="Corte", duracion_min=30, precio=25000)
        self.barba = Servicio.objects.create(nombre="Barba", duracion_min=30, precio=20000)
        self.b = Barbero.objects.create(nombre="Andrés", comision_servicio_pct=40, comision_producto_pct=10)
        self.b.servicios.set([self.corte, self.barba])
        self.dia = manana()
        HorarioLaboral.objects.create(barbero=self.b, dia_semana=self.dia.weekday(), hora_inicio=time(9), hora_fin=time(11))
        self.cliente = Cliente.objects.create(nombre="Juan Pérez", telefono="+573001112233")


class DisponibilidadTests(Base):
    def test_slots_respetan_turno_y_duracion(self):
        slots = disp.horarios_libres(self.b, self.dia, 60)
        horas = [timezone.localtime(s.inicio).strftime("%H:%M") for s in slots]
        self.assertEqual(horas[0], "09:00")
        self.assertEqual(horas[-1], "10:00")  # 10:00 + 60 = 11:00 justo al cierre

    def test_cita_y_bloqueo_ocupan(self):
        disp.crear_cita(cliente=self.cliente, barbero=self.b, servicios=[self.corte], inicio=en(self.dia, 9))
        Bloqueo.objects.create(barbero=self.b, inicio=en(self.dia, 10), fin=en(self.dia, 10, 30))
        horas = {timezone.localtime(s.inicio).strftime("%H:%M") for s in disp.horarios_libres(self.b, self.dia, 30)}
        self.assertNotIn("09:00", horas)
        self.assertNotIn("09:15", horas)
        self.assertNotIn("10:00", horas)
        self.assertIn("09:30", horas)
        self.assertIn("10:30", horas)

    def test_no_permite_doble_reserva(self):
        disp.crear_cita(cliente=self.cliente, barbero=self.b, servicios=[self.corte], inicio=en(self.dia, 9))
        otro = Cliente.objects.create(nombre="Otro", telefono="+573009998877")
        with self.assertRaises(disp.CupoNoDisponible):
            disp.crear_cita(cliente=otro, barbero=self.b, servicios=[self.corte], inicio=en(self.dia, 9, 15))

    def test_retencion_bloquea_a_otra_sesion(self):
        disp.retener(self.b, en(self.dia, 9), 30, "sesion-a")
        with self.assertRaises(disp.CupoNoDisponible):
            disp.retener(self.b, en(self.dia, 9), 30, "sesion-b")
        # la misma sesión sí puede confirmar
        disp.crear_cita(cliente=self.cliente, barbero=self.b, servicios=[self.corte], inicio=en(self.dia, 9),
                        clave_sesion="sesion-a")

    def test_cualquier_barbero_asigna_menos_cargado(self):
        b2 = Barbero.objects.create(nombre="Camilo")
        b2.servicios.set([self.corte])
        HorarioLaboral.objects.create(barbero=b2, dia_semana=self.dia.weekday(), hora_inicio=time(9), hora_fin=time(11))
        disp.crear_cita(cliente=self.cliente, barbero=self.b, servicios=[self.corte], inicio=en(self.dia, 10))
        slots = disp.horarios_combinados([self.b, b2], self.dia, 30)
        self.assertEqual(slots[0].barbero_id, b2.id)


class FlujoReservaTests(Base):
    def test_reserva_completa_con_codigo(self):
        c = self.client
        c.post("/reservar/", {"servicios": [self.corte.id, self.barba.id]})
        c.get(f"/reservar/barbero/?barbero={self.b.id}")
        inicio = en(self.dia, 9).isoformat()
        r = c.post("/reservar/horario/", {"slot": f"{self.b.id}|{inicio}"})
        self.assertRedirects(r, "/reservar/confirmar/")
        c.post("/reservar/codigo/", {"telefono": "311 222 3344"})
<<<<<<< HEAD
        codigo = CODIGO
        r = c.post("/reservar/confirmar/", {"nombre": "Ana", "telefono": "3112223344", "codigo": codigo,
                                            "acepta_datos": "on", "acepta_terminos": "on"})
=======
        codigo = CodigoVerificacion.objects.get(telefono="+573112223344").codigo
        r = c.post("/reservar/confirmar/", {"nombre": "Ana", "telefono": "3112223344", "codigo": codigo, "acepta": "on"})
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
        cita = Cita.objects.get(cliente__telefono="+573112223344")
        self.assertRedirects(r, f"/reservar/listo/{cita.token}/")
        self.assertEqual(cita.precio_total, 45000)
        self.assertEqual(cita.duracion_min, 60)
        self.assertEqual(cita.cliente.puntos, 50)  # bienvenida

    def test_codigo_incorrecto(self):
        c = self.client
        c.post("/reservar/", {"servicios": [self.corte.id]})
        c.get(f"/reservar/barbero/?barbero={self.b.id}")
        c.post("/reservar/horario/", {"slot": f"{self.b.id}|{en(self.dia, 9).isoformat()}"})
        c.post("/reservar/codigo/", {"telefono": "3112223344"})
<<<<<<< HEAD
        r = c.post("/reservar/confirmar/", {"nombre": "Ana", "telefono": "3112223344", "codigo": "000000",
                                            "acepta_datos": "on", "acepta_terminos": "on"})
=======
        r = c.post("/reservar/confirmar/", {"nombre": "Ana", "telefono": "3112223344", "codigo": "000000", "acepta": "on"})
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
        self.assertContains(r, "Código incorrecto")
        self.assertFalse(Cita.objects.exists())

    def test_normalizar_telefono(self):
        self.assertEqual(normalizar_telefono("300 123 4567"), "+573001234567")
        self.assertEqual(normalizar_telefono("+57 300-123-4567"), "+573001234567")
        self.assertIsNone(normalizar_telefono("12345"))


class OperacionesTests(Base):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("rec", password="x")
        self.user.groups.add(Group.objects.create(name="Recepcion"))
        self.caja = Caja.objects.create(abierta_por=self.user, base_inicial=100000)

    def test_cobro_suma_caja_y_puntos(self):
        cita = disp.crear_cita(cliente=self.cliente, barbero=self.b, servicios=[self.corte], inicio=en(self.dia, 9))
        ops.cobrar_cita(cita, medio_pago="efectivo", propina=5000)
        t = self.caja.totales()
        self.assertEqual(t["ingresos"], 30000)
        self.assertEqual(t["efectivo_esperado"], 130000)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.puntos, 25)

    def test_venta_descuenta_stock_y_comision(self):
        p = Producto.objects.create(nombre="Cera", precio_venta=40000, costo=20000, stock=5)
        ops.registrar_inventario(p, MovimientoInventario.VENTA, 2, barbero=self.b)
        p.refresh_from_db()
        self.assertEqual(p.stock, 3)
        cita = disp.crear_cita(cliente=self.cliente, barbero=self.b, servicios=[self.corte], inicio=en(self.dia, 9))
        cita.estado = Cita.COMPLETADA
        cita.save()
        fila = ops.comisiones(self.dia - timedelta(days=2), self.dia)[0]
        self.assertEqual(fila["comision_servicios"], 10000)   # 40% de 25.000
        self.assertEqual(fila["comision_productos"], 8000)    # 10% de 80.000

    def test_permisos_panel(self):
        self.client.login(username="rec", password="x")
        self.assertEqual(self.client.get("/panel/caja/").status_code, 200)
        self.assertEqual(self.client.get("/panel/reportes/").status_code, 403)
<<<<<<< HEAD


# ---------------------------------------------------------------------------------------------
# Protección de datos personales (Ley 1581 de 2012, Ley 2300 de 2023)
# ---------------------------------------------------------------------------------------------
from datetime import date  # noqa: E402

from django.core.cache import cache  # noqa: E402
from django.test import override_settings  # noqa: E402

from core import privacidad as priv  # noqa: E402
from core.festivos import es_festivo, festivos, sumar_dias_habiles  # noqa: E402
from core.models import Consentimiento, RegistroAcceso, SolicitudDatos  # noqa: E402


class FestivosTests(TestCase):
    def test_festivos_2026(self):
        f = festivos(2026)
        self.assertEqual(len(f), 18)
        for d in (date(2026, 1, 12), date(2026, 3, 23), date(2026, 4, 2), date(2026, 4, 3), date(2026, 5, 18),
                  date(2026, 6, 8), date(2026, 6, 15), date(2026, 10, 12), date(2026, 12, 8)):
            self.assertTrue(es_festivo(d), d)

    def test_dias_habiles_saltan_festivo(self):
        # viernes 9 oct 2026 + 1 día hábil: lunes 12 es festivo -> martes 13
        self.assertEqual(sumar_dias_habiles(date(2026, 10, 9), 1), date(2026, 10, 13))


class Ley2300Tests(TestCase):
    def _m(self, y, mo, d, h, mi=0):
        return timezone.make_aware(datetime(y, mo, d, h, mi))

    def test_horarios(self):
        self.assertTrue(priv.en_horario_publicidad(self._m(2026, 10, 14, 10)))    # miércoles
        self.assertFalse(priv.en_horario_publicidad(self._m(2026, 10, 14, 19, 5)))  # después de 7 p. m.
        self.assertTrue(priv.en_horario_publicidad(self._m(2026, 10, 17, 14, 59)))  # sábado
        self.assertFalse(priv.en_horario_publicidad(self._m(2026, 10, 17, 15)))   # sábado 3 p. m.
        self.assertFalse(priv.en_horario_publicidad(self._m(2026, 10, 18, 10)))   # domingo
        self.assertFalse(priv.en_horario_publicidad(self._m(2026, 10, 12, 10)))   # festivo

    def test_requiere_autorizacion_y_frecuencia(self):
        c = Cliente.objects.create(nombre="Ana", telefono="+573001110000")
        m = self._m(2026, 10, 14, 10)
        self.assertFalse(priv.puede_recibir_publicidad(c, m)[0])
        c.acepta_marketing = True
        c.save()
        self.assertTrue(priv.puede_recibir_publicidad(c, m)[0])
        from core import notificaciones
        notificaciones.reactivacion(c)
        self.assertFalse(priv.puede_recibir_publicidad(c, timezone.now())[0])


class ConsentimientoTests(Base):
    def setUp(self):
        super().setUp()
        cache.clear()

    def _hasta_confirmar(self, foto=None):
        c = self.client
        c.post("/reservar/", {"servicios": [self.corte.id]})
        c.get(f"/reservar/barbero/?barbero={self.b.id}")
        c.post("/reservar/horario/", {"slot": f"{self.b.id}|{en(self.dia, 9).isoformat()}"})
        c.post("/reservar/codigo/", {"telefono": "3112223344"})
        return CODIGO

    def test_sin_autorizacion_no_reserva(self):
        codigo = self._hasta_confirmar()
        r = self.client.post("/reservar/confirmar/", {"nombre": "Ana", "telefono": "3112223344", "codigo": codigo})
        self.assertContains(r, "necesitamos tu autorización")
        self.assertFalse(Cita.objects.exists())

    def test_autorizacion_queda_probada_y_marketing_opcional(self):
        codigo = self._hasta_confirmar()
        self.client.post("/reservar/confirmar/", {"nombre": "Ana", "telefono": "3112223344", "codigo": codigo,
                                                  "acepta_datos": "on", "acepta_terminos": "on"},
                         REMOTE_ADDR="190.1.2.3")
        cli = Cliente.objects.get(telefono="+573112223344")
        self.assertEqual(cli.politica_version, "1.0")
        self.assertFalse(cli.acepta_marketing)
        k = Consentimiento.objects.get(cliente=cli, tipo=Consentimiento.TRATAMIENTO)
        self.assertTrue(k.otorgado)
        self.assertEqual(k.ip, "190.1.2.3")
        self.assertIn("mayor de 18", k.texto)

    def test_formulario_sin_casillas_premarcadas(self):
        self._hasta_confirmar()
        html = self.client.get("/reservar/confirmar/").content.decode()
        import re as _re
        for nombre in ("acepta_datos", "acepta_terminos", "acepta_marketing", "acepta_fotos"):
            tag = _re.search(rf'<input[^>]*name="{nombre}"[^>]*>', html).group(0)
            self.assertNotIn("checked", tag, nombre)

    def test_baja_publicidad(self):
        self.cliente.acepta_marketing = True
        self.cliente.save()
        self.client.post(f"/legal/baja/{self.cliente.token_baja}/")
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.acepta_marketing)
        self.assertTrue(Consentimiento.objects.filter(cliente=self.cliente, tipo="marketing", otorgado=False).exists())

    def test_reaceptar_si_cambia_version(self):
        self.cliente.politica_version = "0.9"
        self.cliente.save()
        s = self.client.session
        s["cliente_id"] = self.cliente.id
        s.save()
        r = self.client.get("/perfil/")
        self.assertRedirects(r, "/perfil/politica/?next=/perfil/", fetch_redirect_response=False)


class DerechosTests(Base):
    def setUp(self):
        super().setUp()
        cache.clear()
        priv.aplicar_autorizaciones(self.cliente, sensibles=False, marketing=True)
        s = self.client.session
        s["cliente_id"] = self.cliente.id
        s.save()

    def test_exportar(self):
        disp.crear_cita(cliente=self.cliente, barbero=self.b, servicios=[self.corte], inicio=en(self.dia, 9))
        r = self.client.get("/perfil/mis-datos.json")
        datos = r.json()
        self.assertEqual(datos["datos_personales"]["telefono"], "+573001112233")
        self.assertEqual(len(datos["citas"]), 1)
        self.assertTrue(datos["historial_autorizaciones"])

    def test_eliminar_cuenta_anonimiza_y_conserva_contable(self):
        cita = disp.crear_cita(cliente=self.cliente, barbero=self.b, servicios=[self.corte], inicio=en(self.dia, 9))
        self.client.post("/perfil/eliminar/", {"confirmacion": "ELIMINAR"})
        self.cliente.refresh_from_db()
        cita.refresh_from_db()
        self.assertIsNotNone(self.cliente.anonimizado_en)
        self.assertNotEqual(self.cliente.telefono, "+573001112233")
        self.assertEqual(cita.estado, Cita.CANCELADA)
        self.assertEqual(cita.precio_total, 25000)  # soporte contable conservado
        self.assertTrue(Consentimiento.objects.filter(telefono="+573001112233", otorgado=False).exists())

    def test_radicar_reclamo_con_plazo_habil(self):
        r = self.client.post("/legal/mis-derechos/", {
            "tipo": "supresion", "calidad": "titular", "nombre": "Juan Pérez", "tipo_documento": "CC",
            "documento": "1094123456", "telefono": "3001112233", "email": "juan@example.com",
            "descripcion": "Quiero que borren todos mis datos.", "acepta": "on"})
        self.assertRedirects(r, "/legal/mis-derechos/radicada/")
        s = SolicitudDatos.objects.get()
        self.assertTrue(s.identidad_verificada)
        self.assertEqual(s.vence_en, sumar_dias_habiles(timezone.localdate(), 15))
        self.assertEqual(self.cliente.reclamo_en_tramite, s)

    def test_revocar_fotos_las_borra(self):
        self.client.post("/perfil/autorizaciones/", {"acepta_sensibles": "on", "acepta_whatsapp": "on"})
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.acepta_sensibles)
        self.client.post("/perfil/autorizaciones/", {"acepta_whatsapp": "on"})
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.acepta_sensibles)
        self.assertFalse(self.cliente.acepta_marketing)


class SeguridadTests(Base):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_fotos_no_son_publicas(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.models import FotoReferencia
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
        f = FotoReferencia.objects.create(cliente=self.cliente, archivo=SimpleUploadedFile("x.png", png))
        self.assertEqual(self.client.get(f"/legal/archivos/foto/{f.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/media/" + f.archivo.name).status_code, 404)
        s = self.client.session
        s["cliente_id"] = self.cliente.id
        s.save()
        self.assertEqual(self.client.get(f"/legal/archivos/foto/{f.pk}/").status_code, 200)
        f.archivo.delete()

    def test_archivo_falso_rechazado(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.archivos import validar_archivo
        self.assertIsNotNone(validar_archivo(SimpleUploadedFile("foto.jpg", b"<?php echo 1; ?>")))
        self.assertIsNone(validar_archivo(SimpleUploadedFile("f.jpg", b"\xff\xd8\xff\xe0" + b"0" * 20)))

    def test_limite_codigos(self):
        for _ in range(5):
            cache.delete("lim:otp-ip:127.0.0.1")
            self.client.post("/reservar/codigo/", {"telefono": "3115550000"})
            CodigoVerificacion.objects.update(creado=timezone.now() - timedelta(minutes=5))
        r = self.client.post("/reservar/codigo/", {"telefono": "3115550000"})
        self.assertContains(r, "demasiados códigos")

    def test_bitacora_al_ver_ficha(self):
        u = User.objects.create_user("jefe", password="x", is_superuser=True)
        self.client.force_login(u)
        self.client.get(f"/panel/clientes/{self.cliente.pk}/")
        self.assertTrue(RegistroAcceso.objects.filter(accion="ver_ficha", cliente=self.cliente, usuario=u).exists())

    def test_cabeceras(self):
        r = self.client.get("/")
        self.assertIn("frame-ancestors 'none'", r["Content-Security-Policy"])
        self.assertEqual(r["X-Frame-Options"], "DENY")

    def test_paginas_legales(self):
        for url in ("/legal/privacidad/", "/legal/terminos/", "/legal/cookies/", "/legal/mis-derechos/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get("/"), "www.sic.gov.co")


# ---------------------------------------------------------------------------------------------
# WhatsApp Cloud API y OTP seguro (API de Meta simulada: no sale tráfico real)
# ---------------------------------------------------------------------------------------------
import hashlib  # noqa: E402
import hmac as _hmac  # noqa: E402
import json as _json  # noqa: E402
from unittest import mock  # noqa: E402

from core import otp as _otp  # noqa: E402
from core import whatsapp as wa  # noqa: E402
from core.models import MensajeEnviado  # noqa: E402

WA = {**__import__("django.conf").conf.settings.WHATSAPP, "TOKEN": "EAAG-token-secreto", "PHONE_ID": "1098765",
      "APP_SECRET": "app-secret-de-prueba", "VERIFY_TOKEN": "verificacion-muy-larga-y-aleatoria-123",
      "PLANTILLA_OTP": "codigo_verificacion", "REINTENTOS": 2}
RESPUESTA_OK = {"messaging_product": "whatsapp", "contacts": [{"input": "573001112233", "wa_id": "573001112233"}],
                "messages": [{"id": "wamid.HBgM123"}]}


@override_settings(MENSAJES_BACKEND="whatsapp", WHATSAPP=WA)
class WhatsAppOTPTests(Base):
    def test_payload_plantilla_autenticacion(self):
        with mock.patch("core.whatsapp._post", return_value=RESPUESTA_OK) as post:
            reg, err, debug = _otp.enviar_codigo("+573001112233", "190.1.1.1")
        self.assertIsNone(err)
        self.assertIsNone(debug)  # nunca se muestra el código con WhatsApp activo
        ruta, payload = post.call_args.args
        self.assertEqual(ruta, "1098765/messages")
        self.assertEqual(payload["to"], "573001112233")
        self.assertEqual(payload["type"], "template")
        self.assertEqual(payload["template"]["name"], "codigo_verificacion")
        cuerpo, boton = payload["template"]["components"]
        self.assertEqual(cuerpo["parameters"][0]["text"], CODIGO)
        self.assertEqual((boton["sub_type"], boton["index"], boton["parameters"][0]["text"]), ("url", "0", CODIGO))
        self.assertEqual(reg.wamid, "wamid.HBgM123")

    def test_codigo_no_queda_en_claro(self):
        with mock.patch("core.whatsapp._post", return_value=RESPUESTA_OK):
            reg, _, _ = _otp.enviar_codigo("+573001112233")
        self.assertNotIn(CODIGO, reg.codigo_hash)
        self.assertEqual(len(reg.codigo_hash), 64)
        m = MensajeEnviado.objects.get(tipo="otp")
        self.assertNotIn(CODIGO, m.contenido)
        self.assertIsNone(_otp.verificar("+573001112233", CODIGO))
        self.assertIsNotNone(_otp.verificar("+573001112233", CODIGO))  # un solo uso

    def test_codigo_nuevo_anula_anterior(self):
        with mock.patch("core.whatsapp._post", return_value=RESPUESTA_OK):
            _otp.enviar_codigo("+573001112233")
            CodigoVerificacion.objects.update(creado=timezone.now() - timedelta(minutes=2))
            with mock.patch("core.otp._generar_codigo", return_value="111222"):
                _otp.enviar_codigo("+573001112233")
        self.assertIsNotNone(_otp.verificar("+573001112233", CODIGO))
        self.assertIsNone(_otp.verificar("+573001112233", "111222"))

    def test_numero_sin_whatsapp(self):
        err = wa.WhatsAppError("Meta 400", codigo=131026, http=400)
        with mock.patch("core.whatsapp._post", side_effect=err):
            reg, error, _ = _otp.enviar_codigo("+573001112233")
        self.assertEqual(reg.estado, "fallido")
        self.assertIn("WhatsApp activo", error)

    def test_reintenta_solo_transitorios(self):
        transitorio = wa.WhatsAppError("Meta 500", codigo=131000, http=500, transitorio=True)
        with mock.patch("core.whatsapp.time.sleep"), \
                mock.patch("core.whatsapp._post", side_effect=[transitorio, RESPUESTA_OK]) as post:
            wa.enviar_otp("+573001112233", "123456")
        self.assertEqual(post.call_count, 2)
        definitivo = wa.WhatsAppError("Meta 400", codigo=132001, http=400)
        with mock.patch("core.whatsapp._post", side_effect=definitivo) as post:
            with self.assertRaises(wa.WhatsAppError):
                wa.enviar_otp("+573001112233", "123456")
        self.assertEqual(post.call_count, 1)

    def test_pais_no_permitido(self):
        with mock.patch("core.whatsapp._post") as post:
            reg, error, _ = _otp.enviar_codigo("+4479460000000")
        self.assertIsNone(reg)
        self.assertIn("Colombia", error)
        post.assert_not_called()

    def test_tope_diario_global(self):
        with override_settings(OTP={**__import__("django.conf").conf.settings.OTP, "TOPE_DIARIO_GLOBAL": 1}), \
                mock.patch("core.whatsapp._post", return_value=RESPUESTA_OK):
            self.assertIsNone(_otp.enviar_codigo("+573001112233")[1])
            self.assertIn("en este momento", _otp.enviar_codigo("+573004445566")[1])

    def test_token_no_aparece_en_logs(self):
        err = wa.WhatsAppError("Meta 401: Invalid OAuth access token.", codigo=190, http=401)
        with mock.patch("core.whatsapp._post", side_effect=err), self.assertLogs("core", level="WARNING") as logs:
            _otp.enviar_codigo("+573001112233")
        texto = "\n".join(logs.output)
        self.assertNotIn("EAAG-token-secreto", texto)
        self.assertNotIn(CODIGO, texto)
        self.assertNotIn("+573001112233", texto)  # teléfono enmascarado

    def test_appsecret_proof(self):
        with override_settings(WHATSAPP={**WA, "APPSECRET_PROOF": True}):
            esperado = _hmac.new(b"app-secret-de-prueba", b"EAAG-token-secreto", hashlib.sha256).hexdigest()
            self.assertEqual(wa._appsecret_proof(), esperado)


@override_settings(MENSAJES_BACKEND="whatsapp", WHATSAPP=WA)
class WebhookTests(TestCase):
    def _firmar(self, cuerpo):
        return "sha256=" + _hmac.new(b"app-secret-de-prueba", cuerpo, hashlib.sha256).hexdigest()

    def _evento(self, estado, wamid="wamid.HBgM123", errores=None):
        st = {"id": wamid, "status": estado, "recipient_id": "573001112233", "timestamp": "1760000000"}
        if errores:
            st["errors"] = errores
        return _json.dumps({"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [
            {"field": "messages", "value": {"messaging_product": "whatsapp", "statuses": [st]}}]}]}).encode()

    def test_verificacion_get(self):
        ok = self.client.get("/webhooks/whatsapp/", {"hub.mode": "subscribe", "hub.challenge": "777",
                                                     "hub.verify_token": WA["VERIFY_TOKEN"]})
        self.assertEqual((ok.status_code, ok.content), (200, b"777"))
        malo = self.client.get("/webhooks/whatsapp/", {"hub.mode": "subscribe", "hub.challenge": "1",
                                                       "hub.verify_token": "otro"})
        self.assertEqual(malo.status_code, 403)

    def test_firma_invalida_rechazada(self):
        cuerpo = self._evento("delivered")
        r = self.client.post("/webhooks/whatsapp/", cuerpo, content_type="application/json",
                             HTTP_X_HUB_SIGNATURE_256="sha256=" + "0" * 64)
        self.assertEqual(r.status_code, 403)
        r = self.client.post("/webhooks/whatsapp/", cuerpo, content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_estados_actualizan_y_no_retroceden(self):
        reg = CodigoVerificacion.objects.create(telefono="+573001112233", codigo_hash="x" * 64,
                                                expira=timezone.now(), wamid="wamid.HBgM123", estado="enviado")
        for estado in ("delivered", "read", "sent"):
            cuerpo = self._evento(estado)
            r = self.client.post("/webhooks/whatsapp/", cuerpo, content_type="application/json",
                                 HTTP_X_HUB_SIGNATURE_256=self._firmar(cuerpo))
            self.assertEqual(r.status_code, 200)
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "leido")

    def test_fallo_de_entrega(self):
        m = MensajeEnviado.objects.create(telefono="+573001112233", tipo="otp", contenido="x", wamid="wamid.F1")
        cuerpo = self._evento("failed", "wamid.F1", [{"code": 131026, "title": "Message undeliverable"}])
        self.client.post("/webhooks/whatsapp/", cuerpo, content_type="application/json",
                         HTTP_X_HUB_SIGNATURE_256=self._firmar(cuerpo))
        m.refresh_from_db()
        self.assertEqual((m.estado, m.ok), ("fallido", False))
        self.assertIn("131026", m.error)


class WhatsAppHTTPTests(TestCase):
    """Ejercita _post con un servidor HTTP local que imita a la Graph API."""

    def setUp(self):
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        prueba = self

        class Falso(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                largo = int(self.headers.get("Content-Length", 0))
                prueba.recibido = {"ruta": self.path, "auth": self.headers.get("Authorization"),
                                   "cuerpo": _json.loads(self.rfile.read(largo))}
                if prueba.modo == "error":
                    datos = {"error": {"message": "Template name does not exist", "code": 132001}}
                    self.send_response(404)
                else:
                    datos = RESPUESTA_OK
                    self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(_json.dumps(datos).encode())

        self.servidor = HTTPServer(("127.0.0.1", 0), Falso)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.modo = "ok"
        p = mock.patch("core.whatsapp.GRAPH", f"http://127.0.0.1:{self.servidor.server_port}")
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.servidor.shutdown)

    @override_settings(WHATSAPP={**WA, "APPSECRET_PROOF": True, "API_VERSION": "v25.0"})
    def test_peticion_real(self):
        res = wa.enviar_otp("+573001112233", "654321")
        self.assertEqual(res.wamid, "wamid.HBgM123")
        self.assertTrue(self.recibido["ruta"].startswith("/v25.0/1098765/messages?appsecret_proof="))
        self.assertEqual(self.recibido["auth"], "Bearer EAAG-token-secreto")
        self.assertEqual(self.recibido["cuerpo"]["template"]["components"][1]["parameters"][0]["text"], "654321")

    @override_settings(WHATSAPP=WA)
    def test_error_de_meta(self):
        self.modo = "error"
        with self.assertRaises(wa.WhatsAppError) as ctx:
            wa.enviar_otp("+573001112233", "654321")
        self.assertEqual(ctx.exception.codigo, 132001)
        self.assertTrue(ctx.exception.es_configuracion)
        self.assertFalse(ctx.exception.transitorio)
=======
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad

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


class Base(TestCase):
    def setUp(self):
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
        codigo = CodigoVerificacion.objects.get(telefono="+573112223344").codigo
        r = c.post("/reservar/confirmar/", {"nombre": "Ana", "telefono": "3112223344", "codigo": codigo, "acepta": "on"})
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
        r = c.post("/reservar/confirmar/", {"nombre": "Ana", "telefono": "3112223344", "codigo": "000000", "acepta": "on"})
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

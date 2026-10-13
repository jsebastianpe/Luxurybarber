"""Carga datos de demostración: barberos, servicios, horarios, productos, clientes e historial.

Uso:  python manage.py seed_demo            (solo si la base está vacía)
      python manage.py seed_demo --reset    (borra los datos del negocio y vuelve a cargar)
"""
import random
from datetime import datetime, time, timedelta

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (Barbero, Bloqueo, Caja, Cita, Cliente, HorarioLaboral, MensajeEnviado,
                         MovimientoCaja, MovimientoInventario, Producto, RetencionCupo, Servicio)

SERVICIOS = [
    # nombre, categoria, minutos, precio, ahorro, descripcion
    ("Corte clásico", "corte", 30, 25000, 0, "Tijera y máquina"),
    ("Fade / degradado", "corte", 45, 35000, 0, "Bajo, medio o alto"),
    ("Corte niño (hasta 12 años)", "corte", 30, 20000, 0, ""),
    ("Diseño y líneas", "corte", 15, 10000, 0, "Complemento"),
    ("Arreglo de barba", "barba", 30, 20000, 0, "Perfilado con navaja"),
    ("Barba con toalla caliente", "barba", 40, 28000, 0, "Ritual completo"),
    ("Corte + barba", "combo", 60, 47000, 8000, "Fade o clásico + arreglo"),
    ("Combo VIP", "combo", 90, 70000, 12000, "Corte, barba caliente y masaje"),
    ("Lavado y masaje capilar", "tratamiento", 20, 12000, 0, ""),
    ("Tinte de barba", "tratamiento", 30, 30000, 0, ""),
]

BARBEROS = [
    ("Andrés Gómez", "andres", "Fade, Diseños, Urbano", "Especialista en degradados y diseños. 8 años en la silla.", 4.9, 40),
    ("Camilo Restrepo", "camilo", "Clásico, Barba, Navaja", "Barbería tradicional y afeitado con toalla caliente.", 4.8, 40),
    ("Julián Ospina", "julian", "Fade, Niños, Texturizado", "Paciencia infinita con los más pequeños.", 4.7, 35),
    ("Santiago Vélez", "santiago", "Clásico, Combos, Color", "Cortes ejecutivos y tinte de barba.", 4.8, 35),
]

PRODUCTOS = [
    ("Cera mate fijación fuerte", "CER-01", 38000, 19000, 14, 4, True),
    ("Pomada brillo medio", "POM-01", 35000, 17000, 3, 4, True),
    ("Aceite para barba 30 ml", "ACE-01", 42000, 21000, 9, 3, True),
    ("Shampoo anticaída", "SHA-01", 32000, 15000, 6, 3, True),
    ("Bálsamo para barba", "BAL-01", 36000, 18000, 2, 3, True),
    ("Cuchillas desechables (caja x100)", "CUC-01", 0, 45000, 5, 2, False),
    ("Talco profesional", "TAL-01", 0, 12000, 8, 2, False),
    ("Gel de afeitar 1 L", "GEL-01", 0, 28000, 1, 2, False),
]

NOMBRES = ["Juan", "Carlos", "Mateo", "Sebastián", "Daniel", "Alejandro", "David", "Felipe", "Nicolás", "Samuel",
           "Esteban", "Tomás", "Miguel", "Diego", "Jorge", "Luis", "Andrés", "Kevin", "Brayan", "Simón", "Emiliano",
           "Jerónimo", "Martín", "Pablo", "Óscar", "Ricardo", "Hernán", "Fabián", "Wilson", "Cristian"]
APELLIDOS = ["García", "Rodríguez", "Martínez", "López", "Gómez", "Hernández", "Díaz", "Muñoz", "Álvarez", "Ramírez",
             "Torres", "Castaño", "Zapata", "Arango", "Montoya", "Giraldo", "Valencia", "Cardona", "Mejía", "Osorio"]


class Command(BaseCommand):
    help = "Carga datos de demostración para la barbería"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra datos del negocio antes de cargar")

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(42)
        if opts["reset"]:
            for m in (MovimientoCaja, Caja, MovimientoInventario, MensajeEnviado, RetencionCupo, Cita, Bloqueo,
                      HorarioLaboral, Cliente, Producto, Barbero, Servicio):
                m.objects.all().delete()
            User.objects.filter(username__in=["admin", "recepcion"] + [b[1] for b in BARBEROS]).delete()
        elif Servicio.objects.exists():
            self.stdout.write(self.style.WARNING("Ya hay datos. Usa --reset para recargar."))
            return

        g_admin, _ = Group.objects.get_or_create(name="Admin")
        g_rec, _ = Group.objects.get_or_create(name="Recepcion")
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin12345", first_name="Dueño")
        admin.groups.add(g_admin)
        rec = User.objects.create_user("recepcion", password="recepcion123", first_name="Laura", is_staff=False)
        rec.groups.add(g_rec)

        servicios = []
        for i, (n, cat, mins, precio, ahorro, desc) in enumerate(SERVICIOS):
            servicios.append(Servicio.objects.create(nombre=n, categoria=cat, duracion_min=mins, precio=precio,
                                                     ahorro=ahorro, descripcion=desc, orden=i))
        por_nombre = {s.nombre: s for s in servicios}

        barberos = []
        for i, (nombre, user, esp, bio, cal, pct) in enumerate(BARBEROS):
            u = User.objects.create_user(user, password="barbero123", first_name=nombre.split()[0])
            b = Barbero.objects.create(usuario=u, nombre=nombre, especialidades=esp, bio=bio, calificacion=cal,
                                       comision_servicio_pct=pct, comision_producto_pct=10, orden=i)
            excluir = {"Corte niño (hasta 12 años)"} if user == "camilo" else set()
            if user != "santiago":
                excluir.add("Tinte de barba")
            b.servicios.set([s for s in servicios if s.nombre not in excluir])
            for dia in range(6):  # lunes a sábado, con almuerzo
                HorarioLaboral.objects.create(barbero=b, dia_semana=dia, hora_inicio=time(9), hora_fin=time(13))
                HorarioLaboral.objects.create(barbero=b, dia_semana=dia, hora_inicio=time(14), hora_fin=time(20))
            if user in ("andres", "julian"):
                HorarioLaboral.objects.create(barbero=b, dia_semana=6, hora_inicio=time(10), hora_fin=time(15))
            barberos.append(b)

        for n, sku, pv, costo, stock, minimo, venta in PRODUCTOS:
            Producto.objects.create(nombre=n, sku=sku, precio_venta=pv, costo=costo, stock=stock,
                                    stock_minimo=minimo, para_venta=venta)

        # Clientes
        clientes = []
        usados = set()
        for i in range(48):
            while True:
                nombre = f"{rnd.choice(NOMBRES)} {rnd.choice(APELLIDOS)}"
                if nombre not in usados:
                    usados.add(nombre)
                    break
            c = Cliente.objects.create(
                nombre=nombre, telefono=f"+57300{1000000 + i:07d}",
                pref_maquina=rnd.choice(["", "1 a los lados, 3 arriba", "0.5 lados, tijera arriba", "2 parejo"]),
                pref_estilo=rnd.choice(["", "Fade medio", "Clásico con raya", "Texturizado", "Mid fade + diseño"]),
                pref_barba=rnd.choice(["", "Perfilada", "Corta pareja", "Sin barba"]),
                barbero_preferido=rnd.choice(barberos + [None]),
            )
            clientes.append(c)
        # Cliente de demo fácil de recordar
        demo = Cliente.objects.create(nombre="Cliente Demo", telefono="+573001234567", pref_maquina="1 lados, 3 arriba",
                                      pref_estilo="Fade medio", barbero_preferido=barberos[0], puntos=120)
        clientes.append(demo)

        # Historial de citas: últimos 100 días + próximos 5 días
        tz = timezone.get_current_timezone()
        hoy = timezone.localdate()
        ahora = timezone.now()
        pesos = [(por_nombre["Fade / degradado"], 30), (por_nombre["Corte clásico"], 18), (por_nombre["Corte + barba"], 22),
                 (por_nombre["Arreglo de barba"], 10), (por_nombre["Combo VIP"], 6), (por_nombre["Corte niño (hasta 12 años)"], 6),
                 (por_nombre["Barba con toalla caliente"], 5), (por_nombre["Lavado y masaje capilar"], 3)]
        lista, w = zip(*pesos)
        # Clientes "fieles" (activos) vs. que dejaron de venir
        perfil_cliente = {c.id: rnd.choice(["fiel", "fiel", "regular", "inactivo60", "inactivo35", "inactivo95"]) for c in clientes}
        perfil_cliente[demo.id] = "fiel"
        # Demanda por hora: picos 11-12 y 17-19, sábados altos
        demanda_hora = {9: .35, 10: .5, 11: .7, 12: .65, 14: .4, 15: .45, 16: .55, 17: .8, 18: .9, 19: .75}
        demanda_dia = {0: .55, 1: .5, 2: .6, 3: .65, 4: .85, 5: 1.0, 6: .5}

        creadas = 0
        for delta in range(-100, 6):
            d = hoy + timedelta(days=delta)
            for b in barberos:
                for h in b.horarios.filter(dia_semana=d.weekday()):
                    cursor = datetime.combine(d, h.hora_inicio).replace(tzinfo=tz)
                    fin_turno = datetime.combine(d, h.hora_fin).replace(tzinfo=tz)
                    while cursor < fin_turno:
                        prob = demanda_hora.get(cursor.hour, .3) * demanda_dia[d.weekday()]
                        if delta > 0:
                            prob *= .45  # el futuro está menos lleno
                        if delta == 0 and cursor < ahora:
                            prob *= 1
                        s = rnd.choices(lista, w)[0]
                        if s not in b.servicios.all():
                            s = por_nombre["Corte clásico"]
                        fin = cursor + timedelta(minutes=s.duracion_min)
                        if fin > fin_turno or rnd.random() > prob:
                            cursor += timedelta(minutes=15 if rnd.random() < .5 else 30)
                            continue
                        candidatos = [c for c in clientes if self._puede(perfil_cliente[c.id], delta)]
                        cliente = rnd.choice(candidatos)
                        if fin <= ahora:
                            estado = rnd.choices([Cita.COMPLETADA, Cita.NO_SHOW, Cita.CANCELADA], [88, 6, 6])[0]
                        elif cursor <= ahora < fin:
                            estado = Cita.EN_SILLA
                        else:
                            estado = rnd.choices([Cita.CONFIRMADA, Cita.PENDIENTE], [80, 20])[0]
                        cita = Cita.objects.create(cliente=cliente, barbero=b, inicio=cursor, fin=fin, estado=estado,
                                                   precio_total=s.precio, origen=rnd.choice(["web", "web", "web", "panel", "walkin"]),
                                                   pagada=estado == Cita.COMPLETADA and delta < 0)
                        cita.servicios.set([s])
                        creadas += 1
                        if estado == Cita.COMPLETADA:
                            cliente.puntos += s.precio // 1000
                            if not cliente.ultima_visita or fin > cliente.ultima_visita:
                                cliente.ultima_visita = fin
                        if estado == Cita.NO_SHOW:
                            cliente.no_shows += 1
                        cursor = fin
        for c in clientes:
            c.save()

        # Ventas y uso de productos
        prods = list(Producto.objects.all())
        for delta in range(-60, 0):
            d = hoy + timedelta(days=delta)
            for _ in range(rnd.randint(0, 3)):
                p = rnd.choice(prods)
                tipo = MovimientoInventario.VENTA if p.para_venta else MovimientoInventario.USO
                MovimientoInventario.objects.create(
                    producto=p, tipo=tipo, cantidad=1, barbero=rnd.choice(barberos),
                    precio_unitario=p.precio_venta if tipo == MovimientoInventario.VENTA else p.costo,
                    fecha=datetime.combine(d, time(rnd.randint(9, 19), 0)).replace(tzinfo=tz),
                )

        # Caja de hoy abierta con lo ya cobrado
        caja = Caja.objects.create(abierta_por=rec, base_inicial=150000)
        for c in Cita.objects.filter(inicio__date=hoy, estado=Cita.COMPLETADA):
            MovimientoCaja.objects.create(caja=caja, tipo=MovimientoCaja.INGRESO, concepto=f"Servicio: {c.nombres_servicios}",
                                          monto=c.precio_total, propina=rnd.choice([0, 0, 2000, 5000]),
                                          medio_pago=rnd.choice(["efectivo", "nequi", "daviplata", "tarjeta"]),
                                          cita=c, barbero=c.barbero, usuario=rec, fecha=c.fin)
            c.pagada = True
            c.save(update_fields=["pagada"])

        # Bloqueo de ejemplo
        Bloqueo.objects.create(barbero=barberos[2], inicio=datetime.combine(hoy + timedelta(days=1), time(16)).replace(tzinfo=tz),
                               fin=datetime.combine(hoy + timedelta(days=1), time(17)).replace(tzinfo=tz), motivo="Cita médica")

        self.stdout.write(self.style.SUCCESS(f"Listo: {len(barberos)} barberos, {len(servicios)} servicios, "
                                             f"{len(clientes)} clientes, {creadas} citas."))
        self.stdout.write("Usuarios del panel (/panel/):")
        self.stdout.write("  admin / admin12345        (dueño, ve todo)")
        self.stdout.write("  recepcion / recepcion123  (agenda, caja, clientes)")
        self.stdout.write("  andres / barbero123       (barbero: su agenda y comisiones)")
        self.stdout.write("Cliente demo para /acceso/: 300 123 4567 (el código aparece en pantalla y en la terminal)")

    @staticmethod
    def _puede(perfil, delta):
        if perfil == "inactivo95":
            return delta < -94
        if perfil == "inactivo60":
            return delta < -60
        if perfil == "inactivo35":
            return delta < -35
        return True

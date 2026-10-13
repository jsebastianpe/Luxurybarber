import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def _token():
    return secrets.token_urlsafe(16)


class Servicio(models.Model):
    CATEGORIAS = [
        ("corte", "Cortes"),
        ("barba", "Barba"),
        ("combo", "Combos"),
        ("tratamiento", "Tratamientos"),
    ]
    nombre = models.CharField(max_length=80)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default="corte")
    descripcion = models.CharField(max_length=160, blank=True)
    duracion_min = models.PositiveIntegerField(default=30)
    precio = models.PositiveIntegerField(help_text="Precio en COP, sin decimales")
    ahorro = models.PositiveIntegerField(default=0, help_text="Ahorro mostrado en combos (COP)")
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre


class Barbero(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="barbero"
    )
    nombre = models.CharField(max_length=80)
    slug = models.SlugField(unique=True, blank=True)
    foto_url = models.URLField(blank=True)
    bio = models.CharField(max_length=200, blank=True)
    especialidades = models.CharField(max_length=120, blank=True, help_text="Separadas por coma")
    calificacion = models.DecimalField(max_digits=2, decimal_places=1, default=Decimal("5.0"))
    servicios = models.ManyToManyField(Servicio, related_name="barberos", blank=True)
    comision_servicio_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("40"))
    comision_producto_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("10"))
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden", "nombre"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    @property
    def lista_especialidades(self):
        return [e.strip() for e in self.especialidades.split(",") if e.strip()]

    @property
    def iniciales(self):
        return "".join(p[0] for p in self.nombre.split()[:2]).upper()

    def __str__(self):
        return self.nombre


class HorarioLaboral(models.Model):
    DIAS = [(0, "Lunes"), (1, "Martes"), (2, "Miércoles"), (3, "Jueves"), (4, "Viernes"), (5, "Sábado"), (6, "Domingo")]
    barbero = models.ForeignKey(Barbero, on_delete=models.CASCADE, related_name="horarios")
    dia_semana = models.IntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        ordering = ["barbero", "dia_semana", "hora_inicio"]

    def __str__(self):
        return f"{self.barbero} {self.get_dia_semana_display()} {self.hora_inicio}-{self.hora_fin}"


class Bloqueo(models.Model):
    """Descansos, almuerzo, vacaciones o cualquier franja no disponible."""
    barbero = models.ForeignKey(Barbero, on_delete=models.CASCADE, related_name="bloqueos")
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    motivo = models.CharField(max_length=80, default="Bloqueado")

    def __str__(self):
        return f"{self.barbero}: {self.motivo}"


class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, unique=True, help_text="Formato +57XXXXXXXXXX")
    email = models.EmailField(blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    barbero_preferido = models.ForeignKey(Barbero, null=True, blank=True, on_delete=models.SET_NULL)
    pref_maquina = models.CharField("Número de máquina", max_length=40, blank=True)
    pref_estilo = models.CharField("Estilo preferido", max_length=120, blank=True)
    pref_barba = models.CharField("Tipo de barba", max_length=80, blank=True)
    notas = models.TextField(blank=True, help_text="Notas internas del equipo")
    puntos = models.IntegerField(default=0)
    acepta_whatsapp = models.BooleanField(default=True)
    no_shows = models.PositiveIntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)
    ultima_visita = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def primer_nombre(self):
        return self.nombre.split()[0] if self.nombre else ""

    @property
    def dias_inactivo(self):
        if not self.ultima_visita:
            return None
        return (timezone.now() - self.ultima_visita).days


class FotoReferencia(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="fotos")
    archivo = models.FileField(upload_to="referencias/%Y/%m/")
    descripcion = models.CharField(max_length=120, blank=True)
    es_resultado = models.BooleanField(default=False, help_text="Foto del corte terminado (vs. referencia)")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]


class Cita(models.Model):
    PENDIENTE, CONFIRMADA, EN_SILLA, COMPLETADA, NO_SHOW, CANCELADA = (
        "pendiente", "confirmada", "en_silla", "completada", "no_show", "cancelada",
    )
    ESTADOS = [
        (PENDIENTE, "Pendiente de confirmar"),
        (CONFIRMADA, "Confirmada"),
        (EN_SILLA, "En silla"),
        (COMPLETADA, "Completada"),
        (NO_SHOW, "No-show"),
        (CANCELADA, "Cancelada"),
    ]
    ACTIVAS = [PENDIENTE, CONFIRMADA, EN_SILLA, COMPLETADA]  # ocupan agenda

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="citas")
    barbero = models.ForeignKey(Barbero, on_delete=models.PROTECT, related_name="citas")
    servicios = models.ManyToManyField(Servicio, related_name="citas")
    inicio = models.DateTimeField(db_index=True)
    fin = models.DateTimeField()
    estado = models.CharField(max_length=12, choices=ESTADOS, default=CONFIRMADA)
    precio_total = models.PositiveIntegerField(default=0)
    notas_cliente = models.CharField(max_length=240, blank=True)
    origen = models.CharField(max_length=12, default="web", choices=[("web", "Web"), ("panel", "Panel"), ("walkin", "Sin reserva")])
    token = models.CharField(max_length=32, unique=True, default=_token)
    pagada = models.BooleanField(default=False)
    recordatorio_24h = models.BooleanField(default=False)
    recordatorio_2h = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["inicio"]

    def __str__(self):
        return f"{self.cliente} con {self.barbero} {timezone.localtime(self.inicio):%Y-%m-%d %H:%M}"

    @property
    def duracion_min(self):
        return int((self.fin - self.inicio).total_seconds() // 60)

    @property
    def nombres_servicios(self):
        return " + ".join(s.nombre for s in self.servicios.all())

    @property
    def es_futura(self):
        return self.inicio > timezone.now()

    def puede_cancelar_gratis(self):
        horas = settings.BARBERIA["CANCELACION_HORAS"]
        return self.inicio - timezone.now() >= timedelta(hours=horas)


class RetencionCupo(models.Model):
    """Reserva temporal de un horario mientras el cliente confirma."""
    barbero = models.ForeignKey(Barbero, on_delete=models.CASCADE)
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    clave_sesion = models.CharField(max_length=64, db_index=True)
    expira = models.DateTimeField()

    @property
    def vigente(self):
        return self.expira > timezone.now()


class CodigoVerificacion(models.Model):
    telefono = models.CharField(max_length=20, db_index=True)
    codigo = models.CharField(max_length=6)
    expira = models.DateTimeField()
    intentos = models.PositiveIntegerField(default=0)
    usado = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)


class MensajeEnviado(models.Model):
    TIPOS = [
        ("otp", "Código de verificación"),
        ("confirmacion", "Confirmación de cita"),
        ("recordatorio_24h", "Recordatorio 24 h"),
        ("recordatorio_2h", "Recordatorio 2 h"),
        ("reactivacion", "Cliente inactivo"),
        ("cancelacion", "Cancelación"),
    ]
    telefono = models.CharField(max_length=20)
    cliente = models.ForeignKey(Cliente, null=True, blank=True, on_delete=models.SET_NULL)
    cita = models.ForeignKey(Cita, null=True, blank=True, on_delete=models.SET_NULL)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    canal = models.CharField(max_length=12, default="consola")
    contenido = models.TextField()
    ok = models.BooleanField(default=True)
    enviado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado"]


# ---------------- Inventario ----------------
class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    sku = models.CharField(max_length=30, blank=True)
    precio_venta = models.PositiveIntegerField(default=0)
    costo = models.PositiveIntegerField(default=0)
    stock = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=3)
    para_venta = models.BooleanField(default=True, help_text="Si no, es solo de uso interno")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def stock_bajo(self):
        return self.stock <= self.stock_minimo


class MovimientoInventario(models.Model):
    ENTRADA, VENTA, USO, AJUSTE = "entrada", "venta", "uso", "ajuste"
    TIPOS = [(ENTRADA, "Entrada / compra"), (VENTA, "Venta"), (USO, "Uso interno"), (AJUSTE, "Ajuste")]
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=10, choices=TIPOS)
    cantidad = models.IntegerField(help_text="Positiva; el signo lo da el tipo (ajuste admite negativos)")
    barbero = models.ForeignKey(Barbero, null=True, blank=True, on_delete=models.SET_NULL)
    precio_unitario = models.PositiveIntegerField(default=0)
    nota = models.CharField(max_length=120, blank=True)
    fecha = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-fecha"]

    @property
    def delta(self):
        if self.tipo == self.ENTRADA:
            return abs(self.cantidad)
        if self.tipo in (self.VENTA, self.USO):
            return -abs(self.cantidad)
        return self.cantidad


# ---------------- Caja ----------------
class Caja(models.Model):
    fecha = models.DateField(default=timezone.localdate)
    abierta_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    base_inicial = models.PositiveIntegerField(default=0)
    abierta_en = models.DateTimeField(auto_now_add=True)
    cerrada_en = models.DateTimeField(null=True, blank=True)
    efectivo_contado = models.IntegerField(null=True, blank=True)
    nota_cierre = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-abierta_en"]

    @property
    def abierta(self):
        return self.cerrada_en is None

    def totales(self):
        movs = self.movimientos.all()
        ingresos = sum(m.monto + m.propina for m in movs if m.tipo == MovimientoCaja.INGRESO)
        egresos = sum(m.monto for m in movs if m.tipo == MovimientoCaja.EGRESO)
        por_medio = {}
        for m in movs:
            signo = 1 if m.tipo == MovimientoCaja.INGRESO else -1
            por_medio[m.medio_pago] = por_medio.get(m.medio_pago, 0) + signo * (m.monto + m.propina)
        efectivo_esperado = self.base_inicial + por_medio.get("efectivo", 0)
        propinas = sum(m.propina for m in movs)
        return {
            "ingresos": ingresos,
            "egresos": egresos,
            "neto": ingresos - egresos,
            "por_medio": por_medio,
            "efectivo_esperado": efectivo_esperado,
            "propinas": propinas,
        }


class MovimientoCaja(models.Model):
    INGRESO, EGRESO = "ingreso", "egreso"
    MEDIOS = [
        ("efectivo", "Efectivo"),
        ("nequi", "Nequi"),
        ("daviplata", "Daviplata"),
        ("tarjeta", "Tarjeta"),
        ("transferencia", "Transferencia"),
    ]
    caja = models.ForeignKey(Caja, on_delete=models.CASCADE, related_name="movimientos")
    tipo = models.CharField(max_length=8, choices=[(INGRESO, "Ingreso"), (EGRESO, "Egreso")])
    concepto = models.CharField(max_length=120)
    monto = models.PositiveIntegerField()
    propina = models.PositiveIntegerField(default=0)
    medio_pago = models.CharField(max_length=15, choices=MEDIOS, default="efectivo")
    cita = models.ForeignKey(Cita, null=True, blank=True, on_delete=models.SET_NULL, related_name="pagos")
    barbero = models.ForeignKey(Barbero, null=True, blank=True, on_delete=models.SET_NULL)
    movimiento_inventario = models.ForeignKey(MovimientoInventario, null=True, blank=True, on_delete=models.SET_NULL)
    fecha = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-fecha"]

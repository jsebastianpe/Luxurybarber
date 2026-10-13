"""Reglas de negocio del panel: cobros, puntos, inventario y comisiones."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (Barbero, Caja, Cita, Cliente, MovimientoCaja,
                     MovimientoInventario, Producto)

CFG = settings.BARBERIA


def caja_abierta():
    return Caja.objects.filter(cerrada_en__isnull=True).order_by("-abierta_en").first()


def puntos_por(monto):
    return int(monto // 1000) * CFG["PUNTOS_POR_MIL"]


@transaction.atomic
def cobrar_cita(cita: Cita, *, medio_pago, propina=0, usuario=None, monto=None):
    caja = caja_abierta()
    if caja is None:
        raise ValueError("Abre la caja antes de cobrar.")
    if cita.pagada:
        raise ValueError("Esta cita ya fue cobrada.")
    monto = cita.precio_total if monto is None else monto
    MovimientoCaja.objects.create(
        caja=caja, tipo=MovimientoCaja.INGRESO, concepto=f"Servicio: {cita.nombres_servicios}",
        monto=monto, propina=propina, medio_pago=medio_pago, cita=cita, barbero=cita.barbero, usuario=usuario,
    )
    cita.pagada = True
    if cita.estado != Cita.COMPLETADA:
        cita.estado = Cita.COMPLETADA
    cita.save(update_fields=["pagada", "estado"])
    Cliente.objects.filter(pk=cita.cliente_id).update(
        puntos=F("puntos") + puntos_por(monto), ultima_visita=cita.fin
    )
    return caja


@transaction.atomic
def registrar_inventario(producto: Producto, tipo, cantidad, *, barbero=None, usuario=None, nota="",
                         medio_pago="efectivo"):
    mov = MovimientoInventario.objects.create(
        producto=producto, tipo=tipo, cantidad=cantidad, barbero=barbero, usuario=usuario, nota=nota,
        precio_unitario=producto.precio_venta if tipo == MovimientoInventario.VENTA else producto.costo,
    )
    Producto.objects.filter(pk=producto.pk).update(stock=F("stock") + mov.delta)
    if tipo == MovimientoInventario.VENTA:
        caja = caja_abierta()
        if caja is None:
            raise ValueError("Abre la caja antes de vender productos.")
        MovimientoCaja.objects.create(
            caja=caja, tipo=MovimientoCaja.INGRESO, concepto=f"Venta: {cantidad} × {producto.nombre}",
            monto=producto.precio_venta * abs(cantidad), medio_pago=medio_pago, barbero=barbero,
            movimiento_inventario=mov, usuario=usuario,
        )
    return mov


def comisiones(desde, hasta, barbero=None):
    """Liquidación por barbero entre dos fechas (inclusive)."""
    citas = Cita.objects.filter(estado=Cita.COMPLETADA, inicio__date__gte=desde, inicio__date__lte=hasta)
    ventas = MovimientoInventario.objects.filter(
        tipo=MovimientoInventario.VENTA, fecha__date__gte=desde, fecha__date__lte=hasta, barbero__isnull=False
    )
    propinas = MovimientoCaja.objects.filter(fecha__date__gte=desde, fecha__date__lte=hasta, barbero__isnull=False)
    barberos = Barbero.objects.filter(activo=True)
    if barbero:
        barberos = barberos.filter(pk=barbero.pk)
    filas = []
    for b in barberos:
        cb = citas.filter(barbero=b)
        servicios_total = sum(c.precio_total for c in cb)
        productos_total = sum(v.precio_unitario * abs(v.cantidad) for v in ventas.filter(barbero=b))
        com_serv = Decimal(servicios_total) * b.comision_servicio_pct / 100
        com_prod = Decimal(productos_total) * b.comision_producto_pct / 100
        prop = sum(p.propina for p in propinas.filter(barbero=b))
        filas.append({
            "barbero": b,
            "citas": cb.count(),
            "servicios_total": servicios_total,
            "pct_servicio": b.comision_servicio_pct,
            "comision_servicios": int(com_serv),
            "productos_total": productos_total,
            "pct_producto": b.comision_producto_pct,
            "comision_productos": int(com_prod),
            "propinas": prop,
            "total_pagar": int(com_serv + com_prod) + prop,
        })
    return filas


def reportes(desde, hasta):
    citas = list(
        Cita.objects.filter(inicio__date__gte=desde, inicio__date__lte=hasta)
        .select_related("barbero").prefetch_related("servicios")
    )
    # Mapa de calor: día de la semana × hora (citas que ocupan agenda)
    heat = defaultdict(int)
    for c in citas:
        if c.estado in Cita.ACTIVAS:
            ini = timezone.localtime(c.inicio)
            heat[(ini.weekday(), ini.hour)] += 1
    horas = list(range(8, 21))
    heatmap = [[h - 8, d, heat.get((d, h), 0)] for d in range(7) for h in horas]

    # Servicios por ingreso
    serv = defaultdict(lambda: {"veces": 0, "ingreso": 0, "minutos": 0})
    for c in citas:
        if c.estado == Cita.COMPLETADA:
            for s in c.servicios.all():
                serv[s.nombre]["veces"] += 1
                serv[s.nombre]["ingreso"] += s.precio
                serv[s.nombre]["minutos"] += s.duracion_min
    servicios = sorted(
        ({"nombre": k, **v, "por_hora": int(v["ingreso"] / (v["minutos"] / 60)) if v["minutos"] else 0}
         for k, v in serv.items()),
        key=lambda x: -x["ingreso"],
    )

    # Rendimiento por barbero
    dias = (hasta - desde).days + 1
    rend = []
    for b in Barbero.objects.filter(activo=True):
        cb = [c for c in citas if c.barbero_id == b.id]
        comp = [c for c in cb if c.estado == Cita.COMPLETADA]
        no_show = [c for c in cb if c.estado == Cita.NO_SHOW]
        min_trab = sum(c.duracion_min for c in comp)
        min_disp = 0
        for i in range(dias):
            d = desde + timedelta(days=i)
            for h in b.horarios.filter(dia_semana=d.weekday()):
                min_disp += (h.hora_fin.hour * 60 + h.hora_fin.minute) - (h.hora_inicio.hour * 60 + h.hora_inicio.minute)
        ingreso = sum(c.precio_total for c in comp)
        visitas_cliente = defaultdict(int)
        for c in comp:
            visitas_cliente[c.cliente_id] += 1
        clientes = set(visitas_cliente)
        recurrentes = {cid for cid, n in visitas_cliente.items() if n > 1}
        rend.append({
            "barbero": b,
            "citas": len(comp),
            "ingreso": ingreso,
            "ticket": int(ingreso / len(comp)) if comp else 0,
            "ocupacion": round(100 * min_trab / min_disp) if min_disp else 0,
            "no_shows": len(no_show),
            "retencion": round(100 * len(recurrentes) / len(clientes)) if clientes else 0,
        })
    rend.sort(key=lambda r: -r["ingreso"])
    total = sum(c.precio_total for c in citas if c.estado == Cita.COMPLETADA)
    return {
        "heatmap": heatmap,
        "horas": [f"{h % 12 or 12} {'a' if h < 12 else 'p'}" for h in horas],
        "servicios": servicios,
        "rendimiento": rend,
        "ingreso_total": total,
        "citas_total": sum(1 for c in citas if c.estado == Cita.COMPLETADA),
        "no_shows": sum(1 for c in citas if c.estado == Cita.NO_SHOW),
    }

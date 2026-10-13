"""Django Admin = módulo de Configuración (servicios, barberos, horarios, productos)."""
from django.contrib import admin

from .models import (Barbero, Bloqueo, Caja, Cita, Cliente, CodigoVerificacion, FotoReferencia,
                     HorarioLaboral, MensajeEnviado, MovimientoCaja, MovimientoInventario, Producto,
                     Servicio)


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "duracion_min", "precio", "activo", "orden")
    list_editable = ("precio", "duracion_min", "activo", "orden")
    list_filter = ("categoria", "activo")


class HorarioInline(admin.TabularInline):
    model = HorarioLaboral
    extra = 1


@admin.register(Barbero)
class BarberoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "usuario", "comision_servicio_pct", "comision_producto_pct", "activo")
    list_editable = ("comision_servicio_pct", "comision_producto_pct", "activo")
    filter_horizontal = ("servicios",)
    inlines = [HorarioInline]


@admin.register(Bloqueo)
class BloqueoAdmin(admin.ModelAdmin):
    list_display = ("barbero", "inicio", "fin", "motivo")
    list_filter = ("barbero",)


class FotoInline(admin.TabularInline):
    model = FotoReferencia
    extra = 0


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "puntos", "ultima_visita", "no_shows")
    search_fields = ("nombre", "telefono", "email")
    inlines = [FotoInline]


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ("inicio", "cliente", "barbero", "estado", "precio_total", "pagada", "origen")
    list_filter = ("estado", "barbero", "origen", "pagada")
    date_hierarchy = "inicio"
    search_fields = ("cliente__nombre", "cliente__telefono")
    filter_horizontal = ("servicios",)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "stock", "stock_minimo", "precio_venta", "costo", "para_venta", "activo")
    list_editable = ("stock_minimo", "precio_venta", "costo")


admin.site.register(MovimientoInventario)
admin.site.register(Caja)
admin.site.register(MovimientoCaja)
admin.site.register(MensajeEnviado)
admin.site.register(CodigoVerificacion)

"""Django Admin = módulo de Configuración (servicios, barberos, horarios, productos)."""
from django.contrib import admin

<<<<<<< HEAD
from .models import (Barbero, Bloqueo, Caja, Cita, Cliente, Consentimiento, FotoReferencia,
                     HorarioLaboral, MensajeEnviado, MovimientoCaja, MovimientoInventario, Producto,
                     RegistroAcceso, Servicio, SolicitudDatos)
=======
from .models import (Barbero, Bloqueo, Caja, Cita, Cliente, CodigoVerificacion, FotoReferencia,
                     HorarioLaboral, MensajeEnviado, MovimientoCaja, MovimientoInventario, Producto,
                     Servicio)
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad


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
<<<<<<< HEAD
    fields = ("descripcion", "es_resultado", "creado")
    readonly_fields = ("creado",)
    can_delete = True
=======
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
<<<<<<< HEAD
    list_display = ("nombre", "telefono", "puntos", "ultima_visita", "politica_version", "acepta_marketing", "anonimizado_en")
    list_filter = ("acepta_marketing", "acepta_sensibles", "politica_version")
    search_fields = ("nombre", "telefono", "email")
    readonly_fields = ("politica_version", "autorizado_en", "acepta_marketing", "acepta_sensibles", "token_baja", "anonimizado_en")
=======
    list_display = ("nombre", "telefono", "puntos", "ultima_visita", "no_shows")
    search_fields = ("nombre", "telefono", "email")
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
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
<<<<<<< HEAD


class SoloLectura(admin.ModelAdmin):
    """Las pruebas de autorización y la bitácora no se editan ni se borran a mano."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Consentimiento)
class ConsentimientoAdmin(SoloLectura):
    list_display = ("fecha", "telefono", "tipo", "otorgado", "version", "canal", "registrado_por")
    list_filter = ("tipo", "otorgado", "canal", "version")
    search_fields = ("telefono",)


@admin.register(RegistroAcceso)
class RegistroAccesoAdmin(SoloLectura):
    list_display = ("fecha", "usuario", "accion", "cliente", "ip")
    list_filter = ("accion",)


@admin.register(SolicitudDatos)
class SolicitudDatosAdmin(admin.ModelAdmin):
    list_display = ("radicado", "tipo", "estado", "nombre", "recibida_en", "vence_en")
    list_filter = ("tipo", "estado")
    readonly_fields = ("radicado", "recibida_en", "ip")
=======
admin.site.register(CodigoVerificacion)
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad

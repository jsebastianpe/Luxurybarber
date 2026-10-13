from django.contrib.auth import views as auth_views
from django.urls import include, path

from . import views_cliente as c
from . import views_panel as p

cliente = ([
    path("", c.inicio, name="inicio"),
    path("equipo/<slug:slug>/", c.barbero_detalle, name="barbero"),
    path("reservar/", c.reservar_servicio, name="reservar_servicio"),
    path("reservar/servicio/", c.reservar_servicio),
    path("reservar/repetir/", c.repetir, name="repetir"),
    path("reservar/barbero/", c.reservar_barbero, name="reservar_barbero"),
    path("reservar/horario/", c.reservar_horario, name="reservar_horario"),
    path("reservar/horario/slots/", c.horario_slots, name="horario_slots"),
    path("reservar/confirmar/", c.reservar_confirmar, name="reservar_confirmar"),
    path("reservar/codigo/", c.enviar_codigo, name="enviar_codigo"),
    path("reservar/listo/<str:token>/", c.reserva_lista, name="reserva_lista"),
    path("cita/<str:token>.ics", c.cita_ics, name="cita_ics"),
    path("c/<str:token>/", c.un_toque, name="un_toque"),
    path("acceso/", c.acceso, name="acceso"),
    path("salir/", c.salir, name="salir"),
    path("mis-citas/", c.mis_citas, name="mis_citas"),
    path("mis-citas/<str:token>/", c.cita_detalle, name="cita_detalle"),
    path("perfil/", c.perfil, name="perfil"),
    path("perfil/fotos/<int:pk>/borrar/", c.borrar_foto, name="borrar_foto"),
    path("puntos/", c.puntos, name="puntos"),
], "cliente")

panel = ([
    path("", p.hoy, name="hoy"),
    path("ingresar/", auth_views.LoginView.as_view(template_name="panel/login.html"), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("agenda/", p.agenda, name="agenda"),
    path("agenda/cita/<int:pk>/", p.cita_panel, name="cita_panel"),
    path("agenda/cita/<int:pk>/estado/", p.cita_estado, name="cita_estado"),
    path("agenda/cita/nueva/", p.cita_nueva, name="cita_nueva"),
    path("agenda/bloqueo/", p.bloqueo_nuevo, name="bloqueo_nuevo"),
    path("agenda/bloqueo/<int:pk>/borrar/", p.bloqueo_borrar, name="bloqueo_borrar"),
    path("clientes/", p.clientes, name="clientes"),
    path("clientes/<int:pk>/", p.cliente_ficha, name="cliente_ficha"),
    path("caja/", p.caja, name="caja"),
    path("inventario/", p.inventario, name="inventario"),
    path("comisiones/", p.comisiones, name="comisiones"),
    path("marketing/", p.marketing, name="marketing"),
    path("reportes/", p.reportes, name="reportes"),
], "panel")

urlpatterns = [
    path("", include(cliente)),
    path("panel/", include(panel)),
]

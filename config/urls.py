from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Barbería · Configuración"
admin.site.site_title = "Barbería"

urlpatterns = [
    path("admin/", admin.site.urls),   # configuración avanzada (servicios, horarios, personal)
    path("", include("core.urls")),
]
# Los archivos subidos (fotos y soportes) NO se publican en /media/: se entregan
# por vistas que verifican permisos (core.views_legal.foto y adjunto_solicitud).

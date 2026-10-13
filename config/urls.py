<<<<<<< HEAD
=======
from django.conf import settings
from django.conf.urls.static import static
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Barbería · Configuración"
admin.site.site_title = "Barbería"

urlpatterns = [
    path("admin/", admin.site.urls),   # configuración avanzada (servicios, horarios, personal)
    path("", include("core.urls")),
<<<<<<< HEAD
]
# Los archivos subidos (fotos y soportes) NO se publican en /media/: se entregan
# por vistas que verifican permisos (core.views_legal.foto y adjunto_solicitud).
=======
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad

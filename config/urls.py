from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Barbería · Configuración"
admin.site.site_title = "Barbería"

urlpatterns = [
    path("admin/", admin.site.urls),   # configuración avanzada (servicios, horarios, personal)
    path("", include("core.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

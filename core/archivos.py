"""Validación y entrega protegida de archivos subidos (fotos y soportes de solicitudes)."""
import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404

FIRMAS = {
    "jpg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "webp": [b"RIFF"],
    "heic": [],  # se valida por la caja ftyp
    "pdf": [b"%PDF-"],
}


def _tipo_real(cabecera: bytes):
    for tipo, firmas in FIRMAS.items():
        if any(cabecera.startswith(f) for f in firmas):
            if tipo == "webp" and cabecera[8:12] != b"WEBP":
                continue
            return tipo
    if cabecera[4:8] == b"ftyp" and cabecera[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"hevc"):
        return "heic"
    return None


def validar_archivo(f, permitir_pdf=False):
    """Devuelve un mensaje de error o None. Revisa tamaño y firma binaria (no solo la extensión)."""
    if f is None:
        return None
    if f.size > settings.FOTO_MAX_MB * 1024 * 1024:
        return f"El archivo supera {settings.FOTO_MAX_MB} MB."
    cabecera = f.read(16)
    f.seek(0)
    tipo = _tipo_real(cabecera)
    permitidos = {"jpg", "png", "webp", "heic"} | ({"pdf"} if permitir_pdf else set())
    if tipo not in permitidos:
        return "Formato no permitido. Sube una imagen JPG, PNG, WEBP o HEIC" + (" o un PDF." if permitir_pdf else ".")
    return None


def servir(campo_archivo):
    """Entrega un archivo privado sin exponer una URL pública. Llamar solo tras validar permisos."""
    if not campo_archivo:
        raise Http404
    ruta = campo_archivo.path
    if not os.path.exists(ruta):
        raise Http404
    tipo = mimetypes.guess_type(ruta)[0] or "application/octet-stream"
    resp = FileResponse(open(ruta, "rb"), content_type=tipo)
    resp["Cache-Control"] = "private, no-store"
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Content-Disposition"] = "inline"
    return resp

from django.conf import settings


class CabecerasSeguridad:
    """Content-Security-Policy y Permissions-Policy (principio de seguridad, Ley 1581 art. 4 lit. g)."""

    def __init__(self, get_response):
        self.get_response = get_response
        scripts = "'self' 'unsafe-inline' 'unsafe-eval'"  # Alpine.js estándar evalúa expresiones
        if settings.TAILWIND_CDN:
            scripts += " https://cdn.tailwindcss.com"
        self.csp = "; ".join([
            "default-src 'self'",
            f"script-src {scripts}",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob: https:",
            "font-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'",
            "object-src 'none'",
        ])

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/admin/"):
            response.setdefault("Content-Security-Policy", self.csp)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if request.path.startswith("/panel/") or request.path.startswith("/perfil") or request.path.startswith("/mis-citas"):
            response["Cache-Control"] = "no-store"
        return response

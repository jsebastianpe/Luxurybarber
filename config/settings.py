"""Configuración de Barbería App (Django 5)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    valor = os.environ.get(name)
    return default if valor in (None, "") else valor


# Carga simple de .env (sin dependencias externas)
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-inseguro-cambia-esto-en-produccion")
DEBUG = env("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.CabecerasSeguridad",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.negocio",
            ],
            "builtins": ["core.templatetags.barberia"],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite por defecto; en producción define DATABASE_URL-style vars para PostgreSQL
if env("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER", "postgres"),
            "PASSWORD": env("POSTGRES_PASSWORD", ""),
            "HOST": env("POSTGRES_HOST", "localhost"),
            "PORT": env("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "panel:login"
LOGIN_REDIRECT_URL = "panel:hoy"
LOGOUT_REDIRECT_URL = "panel:login"

# --- Reglas del negocio (ajustables) ---
BARBERIA = {
    "NOMBRE": env("BARBERIA_NOMBRE", "Navaja & Cuero"),
    "DIRECCION": env("BARBERIA_DIRECCION", "Cra. 14 # 20-35, Armenia, Quindío"),
    "TELEFONO": env("BARBERIA_TELEFONO", "+57 300 000 0000"),
    "PASO_MINUTOS": 15,             # granularidad de horarios ofrecidos
    "ANTICIPACION_MIN": 30,         # mínimo de minutos antes de poder reservar
    "DIAS_VISIBLES": 14,            # días que muestra el selector
    "RETENCION_MIN": 10,            # minutos que se retiene un cupo
    "CANCELACION_HORAS": 3,         # cancelación gratuita hasta N horas antes
    "PUNTOS_POR_MIL": 1,            # puntos por cada $1.000 COP pagados
    "PUNTOS_BIENVENIDA": 50,
    "INACTIVO_DIAS": [30, 60, 90],
    "TOLERANCIA_LLEGADA_MIN": 10,   # minutos de espera antes de liberar la cita (términos y condiciones)
    "GARANTIA_DIAS": 5,             # días calendario para pedir un retoque sin costo
    "NO_SHOWS_CONFIRMACION": 2,     # desde cuántas inasistencias se exige confirmar por teléfono
    "MEDIOS_PAGO": "efectivo, Nequi, Daviplata, transferencia y tarjeta débito o crédito",
    "HORARIO_ATENCION": env("BARBERIA_HORARIO", "Lunes a sábado de 9:00 a. m. a 8:00 p. m."),
}

# Tailwind: CSS compilado (static/css/tailwind.css) o CDN para prototipar sin compilar
TAILWIND_CDN = env("TAILWIND_CDN", "0") == "1"

# Canal de mensajes: "consola" (desarrollo) o "whatsapp" (WhatsApp Cloud API de Meta)
MENSAJES_BACKEND = env("MENSAJES_BACKEND", "consola")

# --- WhatsApp Cloud API (Meta) ---
# Secretos SOLO por variables de entorno o gestor de secretos; nunca en el código ni en la base de datos.
WHATSAPP = {
    "TOKEN": env("WHATSAPP_TOKEN", ""),                    # token permanente de un usuario del sistema
    "PHONE_ID": env("WHATSAPP_PHONE_ID", ""),              # identificador del número que envía
    "WABA_ID": env("WHATSAPP_WABA_ID", ""),                # cuenta de WhatsApp Business (para crear plantillas)
    "APP_SECRET": env("WHATSAPP_APP_SECRET", ""),          # firma de webhooks y appsecret_proof
    "VERIFY_TOKEN": env("WHATSAPP_VERIFY_TOKEN", ""),      # cadena aleatoria para registrar el webhook
    "API_VERSION": env("WHATSAPP_API_VERSION", "v25.0"),
    "APPSECRET_PROOF": env("WHATSAPP_APPSECRET_PROOF", "0") == "1",
    "TIMEOUT": float(env("WHATSAPP_TIMEOUT", "10")),
    "REINTENTOS": int(env("WHATSAPP_REINTENTOS", "2")),
    "IDIOMA": env("WHATSAPP_IDIOMA", "es"),
    # Plantillas aprobadas en Meta (nombre exacto). Vacío = texto libre (solo funciona dentro de la ventana de 24 h)
    "PLANTILLA_OTP": env("WHATSAPP_PLANTILLA_OTP", "codigo_verificacion"),
    "PLANTILLA_CONFIRMACION": env("WHATSAPP_PLANTILLA_CONFIRMACION", ""),
    "PLANTILLA_RECORDATORIO": env("WHATSAPP_PLANTILLA_RECORDATORIO", ""),
    "PLANTILLA_CANCELACION": env("WHATSAPP_PLANTILLA_CANCELACION", ""),
    "PLANTILLA_PROMOCION": env("WHATSAPP_PLANTILLA_PROMOCION", ""),
    # Códigos de país permitidos para OTP: evita fraude por bombeo de mensajes a destinos caros
    "PAISES_OTP": [p.strip() for p in env("WHATSAPP_PAISES_OTP", "57").split(",") if p.strip()],
}
OTP = {
    "LONGITUD": 6,
    "VIGENCIA_MIN": 10,               # debe coincidir con code_expiration_minutes de la plantilla
    "INTENTOS": 3,
    "REENVIO_SEG": 30,
    "TOPE_DIARIO_GLOBAL": int(env("OTP_TOPE_DIARIO", "500")),  # freno de costos ante abuso
    "PIMIENTA": env("OTP_PIMIENTA", ""),                     # clave HMAC; si está vacía se deriva de SECRET_KEY
}
SITIO_URL = env("SITIO_URL", "http://127.0.0.1:8000")

# --- Protección de datos personales (Ley 1581 de 2012, Decreto 1074 de 2015) ---
# Datos del RESPONSABLE del tratamiento. Deben ser los reales antes de lanzar:
# el chequeo `python manage.py check --deploy` falla si quedan vacíos con DEBUG=0.
RESPONSABLE = {
    "RAZON_SOCIAL": env("RESP_RAZON_SOCIAL", ""),          # Ej.: "Navaja & Cuero S.A.S." o el nombre del dueño
    "TIPO_ID": env("RESP_TIPO_ID", "NIT"),                  # NIT o C.C. (persona natural)
    "NUMERO_ID": env("RESP_NUMERO_ID", ""),                 # Ej.: 901.234.567-8
    "DOMICILIO": env("RESP_DOMICILIO", "Armenia, Quindío"),
    "DIRECCION": env("RESP_DIRECCION", BARBERIA["DIRECCION"]),
    "EMAIL_DATOS": env("RESP_EMAIL_DATOS", ""),             # buzón para consultas y reclamos de habeas data
    "TELEFONO": env("RESP_TELEFONO", BARBERIA["TELEFONO"]),
    "AREA_RESPONSABLE": env("RESP_AREA", "Administración - Oficial de Protección de Datos"),
    "MATRICULA_MERCANTIL": env("RESP_MATRICULA", ""),
}
# Encargados del tratamiento que aparecen en la política (actualízalos con tus proveedores reales
# y firma con cada uno un contrato de transmisión: ver legal/CONTRATO_TRANSMISION.md)
ENCARGADOS = {
    "hosting": env("ENCARGADO_HOSTING", "[Proveedor de hosting]"),
    "hosting_pais": env("ENCARGADO_HOSTING_PAIS", "[País]"),
    "correo": env("ENCARGADO_CORREO", ""),
    "correo_pais": env("ENCARGADO_CORREO_PAIS", ""),
}
POLITICA_VERSION = "1.0"              # súbela cuando cambie sustancialmente la política
POLITICA_VIGENCIA = "2026-10-13"      # fecha de entrada en vigencia (AAAA-MM-DD)
TERMINOS_VERSION = "1.0"

# Plazos de conservación (en días). Ver sección 9 de la política.
RETENCION = {
    "CODIGOS_OTP": 30,                # códigos de verificación
    "MENSAJES": 365,                  # registro de mensajes enviados
    "AUDITORIA": 365 * 2,             # registro de accesos a datos de clientes
    "CLIENTE_INACTIVO": 365 * 3,      # se anonimiza el cliente sin visitas ni citas en 3 años
    "FOTOS_INACTIVO": 365,            # fotos de clientes sin visitas en 1 año
    "SOLICITUDES": 365 * 5,           # prueba de atención de derechos
}

# Mensajes publicitarios: Ley 2300 de 2023 (art. 3 y 5)
HORARIO_PUBLICIDAD = {
    "LUNES_VIERNES": (7, 19),         # 7:00 a. m. a 7:00 p. m.
    "SABADO": (8, 15),                # 8:00 a. m. a 3:00 p. m.
    "DIAS_ENTRE_MENSAJES": 7,         # no más de un mensaje publicitario por semana por cliente
}

# Límites anti-abuso
LIMITES = {
    "OTP_POR_TELEFONO_HORA": 5,
    "OTP_POR_IP_HORA": 15,
    "LOGIN_FALLIDOS": 5,
    "LOGIN_BLOQUEO_MIN": 15,
    "DERECHOS_POR_IP_DIA": 10,
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
if env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}}

# Sesiones y cookies (solo cookies estrictamente necesarias: sesión y CSRF)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FOTO_MAX_MB = 5

# Seguridad en producción (DEBUG=0): HTTPS obligatorio y cabeceras seguras
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env("DJANGO_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    CSRF_TRUSTED_ORIGINS = [o for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Correo (respuestas a consultas y reclamos). En desarrollo se imprime en la terminal.
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", RESPONSABLE["EMAIL_DATOS"] or "no-responder@localhost")

LOGGING = {
    "version": 1,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"core": {"handlers": ["console"], "level": "INFO"}},
}

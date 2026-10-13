"""Configuración de Barbería App (Django 5)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


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
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
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
}

# Tailwind: CSS compilado (static/css/tailwind.css) o CDN para prototipar sin compilar
TAILWIND_CDN = env("TAILWIND_CDN", "0") == "1"

# Canal de mensajes: "consola" (desarrollo) o "whatsapp" (WhatsApp Cloud API de Meta)
MENSAJES_BACKEND = env("MENSAJES_BACKEND", "consola")
WHATSAPP_TOKEN = env("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = env("WHATSAPP_PHONE_ID", "")
SITIO_URL = env("SITIO_URL", "http://127.0.0.1:8000")

LOGGING = {
    "version": 1,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"core": {"handlers": ["console"], "level": "INFO"}},
}

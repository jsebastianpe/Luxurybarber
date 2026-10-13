"""Cliente seguro para la WhatsApp Cloud API de Meta.

Principios de seguridad aplicados:
- El token de acceso vive solo en variables de entorno. Nunca se registra en logs ni se guarda en la base.
- Solo HTTPS hacia graph.facebook.com, con verificación TLS por defecto y tiempo de espera acotado.
- Reintentos solo ante errores transitorios (red, 5xx o códigos de Meta marcados como temporales), con espera
  exponencial. Los errores de límite (429) no se reintentan en caliente, para no empeorar el bloqueo.
- `appsecret_proof` opcional: aunque se filtre el token, no se puede usar sin el app secret.
- Los teléfonos se enmascaran en los logs (Ley 1581: principio de seguridad y circulación restringida).
- El código OTP solo existe en memoria durante el envío. No se registra ni se guarda en texto plano.
"""
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from django.conf import settings
from django.views.decorators.debug import sensitive_variables

log = logging.getLogger("core.whatsapp")

GRAPH = "https://graph.facebook.com"

# Códigos de error de Meta: https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
TRANSITORIOS = {1, 2, 131000, 131016}
LIMITE = {4, 80007, 130429, 131056}
MENSAJES_USUARIO = {
    131026: "No pudimos entregar el código. Verifica que el número tenga WhatsApp activo.",
    131009: "El número no es válido para WhatsApp. Revísalo.",
    131049: "WhatsApp no entregó el mensaje en este momento. Intenta más tarde.",
    131056: "Enviamos varios mensajes seguidos a este número. Espera unos minutos.",
    130429: "Nuestro servicio de mensajes está ocupado. Intenta en unos minutos.",
    80007: "Nuestro servicio de mensajes está ocupado. Intenta en unos minutos.",
    4: "Nuestro servicio de mensajes está ocupado. Intenta en unos minutos.",
}
ERRORES_CONFIG = {0, 10, 100, 190, 132000, 132001, 132005, 132007, 132012, 132015, 132016, 133010, 131042, 131047}


class WhatsAppError(Exception):
    def __init__(self, mensaje, codigo=None, http=None, transitorio=False):
        super().__init__(mensaje)
        self.codigo = codigo
        self.http = http
        self.transitorio = transitorio

    @property
    def para_usuario(self):
        if self.codigo in MENSAJES_USUARIO:
            return MENSAJES_USUARIO[self.codigo]
        return "No pudimos enviar el mensaje por WhatsApp en este momento. Intenta de nuevo en unos minutos."

    @property
    def es_configuracion(self):
        """Error que requiere acción del administrador (token vencido, plantilla inexistente, etc.)."""
        return self.codigo in ERRORES_CONFIG


@dataclass
class Resultado:
    wamid: str
    wa_id: str = ""
    crudo: dict = field(default_factory=dict)


def enmascarar(telefono: str) -> str:
    t = telefono or ""
    return t[:5] + "*" * max(0, len(t) - 8) + t[-3:] if len(t) > 8 else "***"


def configurado() -> bool:
    w = settings.WHATSAPP
    return bool(w["TOKEN"] and w["PHONE_ID"])


@sensitive_variables("token", "secreto")
def _appsecret_proof():
    w = settings.WHATSAPP
    token, secreto = w["TOKEN"], w["APP_SECRET"]
    if not (w["APPSECRET_PROOF"] and secreto):
        return None
    return hmac.new(secreto.encode(), token.encode(), hashlib.sha256).hexdigest()


@sensitive_variables("token", "cuerpo", "payload")
def _post(ruta: str, payload: dict) -> dict:
    """POST a la Graph API. Separado para poder simularlo en pruebas."""
    w = settings.WHATSAPP
    token = w["TOKEN"]
    url = f"{GRAPH}/{w['API_VERSION']}/{ruta}"
    prueba = _appsecret_proof()
    if prueba:
        url += "?" + urllib.parse.urlencode({"appsecret_proof": prueba})
    cuerpo = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=cuerpo, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "barberia-app/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=w["TIMEOUT"]) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            datos = json.loads(e.read().decode() or "{}")
        except ValueError:
            datos = {}
        err = datos.get("error", {})
        codigo = err.get("code")
        transitorio = e.code >= 500 or codigo in TRANSITORIOS
        # El mensaje de Meta no contiene el token; aun así se recorta por prudencia.
        raise WhatsAppError(f"Meta {e.code}: {str(err.get('message', ''))[:200]}", codigo=codigo, http=e.code,
                            transitorio=transitorio and codigo not in LIMITE) from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise WhatsAppError(f"Red: {type(e).__name__}", transitorio=True) from None


@sensitive_variables("token")
def _get(ruta: str, campos: str) -> dict:
    w = settings.WHATSAPP
    token = w["TOKEN"]
    params = {"fields": campos}
    prueba = _appsecret_proof()
    if prueba:
        params["appsecret_proof"] = prueba
    req = urllib.request.Request(f"{GRAPH}/{w['API_VERSION']}/{ruta}?{urllib.parse.urlencode(params)}",
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=w["TIMEOUT"]) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode() or "{}").get("error", {})
        except ValueError:
            err = {}
        raise WhatsAppError(f"Meta {e.code}: {str(err.get('message', ''))[:200]}", codigo=err.get("code"), http=e.code) from None


def info_numero() -> dict:
    """Datos del número emisor: sirve para comprobar que el token y el PHONE_ID son correctos."""
    return _get(settings.WHATSAPP["PHONE_ID"], "display_phone_number,verified_name,quality_rating")


def plantillas() -> list:
    datos = _get(f"{settings.WHATSAPP['WABA_ID']}/message_templates", "name,status,category,language")
    return datos.get("data", [])


def _con_reintentos(ruta, payload):
    intentos = settings.WHATSAPP["REINTENTOS"] + 1
    for n in range(intentos):
        try:
            return _post(ruta, payload)
        except WhatsAppError as e:
            if not e.transitorio or n == intentos - 1:
                raise
            time.sleep(0.5 * (3 ** n))  # 0.5 s, 1.5 s, …
    raise WhatsAppError("Sin respuesta")  # pragma: no cover


def _resultado(datos) -> Resultado:
    try:
        wamid = datos["messages"][0]["id"]
    except (KeyError, IndexError, TypeError):
        raise WhatsAppError("Respuesta de Meta sin identificador de mensaje") from None
    wa_id = ((datos.get("contacts") or [{}])[0]).get("wa_id", "")
    return Resultado(wamid=wamid, wa_id=wa_id, crudo={"messages": datos.get("messages")})


def _destino(telefono: str) -> str:
    digitos = "".join(ch for ch in telefono if ch.isdigit())
    if not 8 <= len(digitos) <= 15:
        raise WhatsAppError("Número inválido", codigo=131009)
    return digitos


def enviar_plantilla(telefono: str, nombre: str, componentes: list, idioma: str | None = None) -> Resultado:
    if not configurado():
        raise WhatsAppError("WhatsApp no está configurado", codigo=190)
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": _destino(telefono),
        "type": "template",
        "template": {"name": nombre, "language": {"code": idioma or settings.WHATSAPP["IDIOMA"]},
                     "components": componentes},
    }
    res = _resultado(_con_reintentos(f"{settings.WHATSAPP['PHONE_ID']}/messages", payload))
    log.info("WhatsApp plantilla=%s a %s wamid=%s", nombre, enmascarar(telefono), res.wamid)
    return res


def enviar_texto(telefono: str, texto: str) -> Resultado:
    """Texto libre: Meta solo lo entrega si el cliente escribió en las últimas 24 h."""
    if not configurado():
        raise WhatsAppError("WhatsApp no está configurado", codigo=190)
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": _destino(telefono),
               "type": "text", "text": {"body": texto[:4096], "preview_url": False}}
    res = _resultado(_con_reintentos(f"{settings.WHATSAPP['PHONE_ID']}/messages", payload))
    log.info("WhatsApp texto a %s wamid=%s", enmascarar(telefono), res.wamid)
    return res


@sensitive_variables("codigo")
def enviar_otp(telefono: str, codigo: str) -> Resultado:
    """Plantilla de autenticación con botón «Copiar código». El código va en el cuerpo y en el botón."""
    if not (codigo.isalnum() and len(codigo) <= 15):
        raise ValueError("Código OTP inválido")
    componentes = [
        {"type": "body", "parameters": [{"type": "text", "text": codigo}]},
        {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": codigo}]},
    ]
    return enviar_plantilla(telefono, settings.WHATSAPP["PLANTILLA_OTP"], componentes)


def parametros_cuerpo(*valores) -> list:
    """Componentes de cuerpo con parámetros {{1}}, {{2}}… (sin saltos de línea: Meta los rechaza)."""
    limpios = [" ".join(str(v).split())[:1000] for v in valores]
    return [{"type": "body", "parameters": [{"type": "text", "text": v} for v in limpios]}]


# ------------------------------------------------------------------------------------------
# Administración de plantillas (comando whatsapp_configurar)
# ------------------------------------------------------------------------------------------
def crear_plantilla_otp(nombre=None, idioma=None, vigencia_min=None) -> dict:
    w = settings.WHATSAPP
    if not (w["TOKEN"] and w["WABA_ID"]):
        raise WhatsAppError("Faltan WHATSAPP_TOKEN o WHATSAPP_WABA_ID")
    payload = {
        "name": nombre or w["PLANTILLA_OTP"],
        "language": idioma or w["IDIOMA"],
        "category": "AUTHENTICATION",
        "message_send_ttl_seconds": (vigencia_min or settings.OTP["VIGENCIA_MIN"]) * 60,
        "components": [
            {"type": "BODY", "add_security_recommendation": True},
            {"type": "FOOTER", "code_expiration_minutes": vigencia_min or settings.OTP["VIGENCIA_MIN"]},
            {"type": "BUTTONS", "buttons": [{"type": "OTP", "otp_type": "COPY_CODE", "text": "Copiar código"}]},
        ],
    }
    return _post(f"{w['WABA_ID']}/message_templates", payload)


# ------------------------------------------------------------------------------------------
# Webhooks
# ------------------------------------------------------------------------------------------
@sensitive_variables("secreto")
def firma_valida(cuerpo: bytes, cabecera: str | None) -> bool:
    """X-Hub-Signature-256 = 'sha256=' + HMAC-SHA256(app_secret, cuerpo crudo). Comparación en tiempo constante."""
    secreto = settings.WHATSAPP["APP_SECRET"]
    if not (secreto and cabecera and cabecera.startswith("sha256=")):
        return False
    esperado = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecera[7:])


def estados_del_webhook(datos: dict):
    """Itera los estados de entrega: (wamid, estado, codigo_error, titulo_error)."""
    for entrada in datos.get("entry", []) or []:
        for cambio in entrada.get("changes", []) or []:
            if cambio.get("field") != "messages":
                continue
            for st in (cambio.get("value") or {}).get("statuses", []) or []:
                err = (st.get("errors") or [{}])[0]
                yield st.get("id", ""), st.get("status", ""), err.get("code"), str(err.get("title", ""))[:120]

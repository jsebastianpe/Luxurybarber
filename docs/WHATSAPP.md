# Configurar WhatsApp Cloud API (Meta) para los códigos de verificación

Cuando un cliente escribe su celular y toca «Enviar código», el servidor crea un código de 6 dígitos. Se lo envía
**a ese mismo número** con una plantilla de autenticación de WhatsApp que trae el botón «Copiar código».
Meta avisa por webhook si el mensaje fue entregado o leído, y la pantalla de reserva lo muestra en vivo.

```
Cliente ─▶ /reservar/codigo/ ─▶ otp.enviar_codigo ─▶ whatsapp.enviar_otp ─▶ Graph API (HTTPS + token)
                                     │ guarda solo HMAC(código)                 │
Meta ─▶ /webhooks/whatsapp/ (firma X-Hub-Signature-256) ─▶ estado: enviado → entregado → leído | fallido
```

## 1. En Meta (una sola vez)

1. **Meta Business Suite → Configuración del negocio.** Activa la verificación en dos pasos para todos los administradores e inicia la *verificación del negocio*, que sube los límites de envío.
2. **developers.facebook.com → Crear app** de tipo *Empresa* y agrega el producto **WhatsApp**.
3. **WhatsApp → Configuración de la API.**
   - Agrega y verifica el número de la barbería. Debe ser un número que no esté en uso en la app de WhatsApp.
   - Copia el **ID del número de teléfono** (`WHATSAPP_PHONE_ID`) y el **ID de la cuenta de WhatsApp Business** (`WHATSAPP_WABA_ID`).
4. **Token permanente.** No uses el token temporal de 24 h.
   - Configuración del negocio → Usuarios del sistema → Agregar (rol *Empleado*).
   - Asígnale la app y la cuenta de WhatsApp.
   - Genera un token **sin vencimiento** con solo los permisos `whatsapp_business_messaging` y `whatsapp_business_management`. Ese es `WHATSAPP_TOKEN`.
5. **App → Configuración → Básica.** Copia la **clave secreta de la app** (`WHATSAPP_APP_SECRET`).
6. **Recomendado.** En App → Configuración → Avanzada, activa **«Requerir clave secreta de la app»** y pon `WHATSAPP_APPSECRET_PROOF=1`. Así, aunque se filtre el token, no se puede usar sin la clave secreta.
7. **Método de pago** en la cuenta de WhatsApp. Las plantillas de autenticación se cobran por mensaje.

## 2. En el servidor (`.env`)

```bash
MENSAJES_BACKEND=whatsapp
SITIO_URL=https://tudominio.com
WHATSAPP_TOKEN=EAAG...                 # token permanente del usuario del sistema
WHATSAPP_PHONE_ID=123456789012345
WHATSAPP_WABA_ID=987654321098765
WHATSAPP_APP_SECRET=...
WHATSAPP_VERIFY_TOKEN=...              # genera uno: python -c "import secrets; print(secrets.token_urlsafe(32))"
WHATSAPP_APPSECRET_PROOF=1
WHATSAPP_PLANTILLA_OTP=codigo_verificacion
WHATSAPP_PAISES_OTP=57                 # solo celulares de Colombia
OTP_PIMIENTA=...                       # otra clave aleatoria de 32+ caracteres
OTP_TOPE_DIARIO=500                    # máximo de códigos por día (freno de costos ante abuso)
```

Guarda estas variables en el gestor de secretos de tu hosting, no en el repositorio. `.env` está en `.gitignore`.

## 3. Crear y aprobar la plantilla del código

```bash
python manage.py whatsapp --verificar             # confirma token y número
python manage.py whatsapp --crear-plantilla-otp   # crea «codigo_verificacion» en español
```

Las plantillas de autenticación tienen un texto predefinido por Meta en español: el código, la recomendación de no compartirlo, el aviso de vencimiento a los 10 minutos y el botón «Copiar código». No se les puede agregar enlaces ni emojis. Espera a que figure como `APPROVED`:

```bash
python manage.py whatsapp --verificar
python manage.py whatsapp --probar 3001234567     # envía un código de prueba a tu celular
```

## 4. Webhook de estados de entrega

En App → WhatsApp → Configuración → Webhook:

- **URL de devolución de llamada:** `https://tudominio.com/webhooks/whatsapp/`
- **Token de verificación:** el valor de `WHATSAPP_VERIFY_TOKEN`
- **Suscribirse al campo:** `messages`

El servidor rechaza con 403 cualquier petición sin una firma `X-Hub-Signature-256` válida.

## 5. Plantillas de los demás mensajes (recomendado)

Fuera de la ventana de 24 h, WhatsApp solo entrega plantillas aprobadas. Crea estas en el Administrador de WhatsApp, en español, y pon su nombre en `.env`:

| Variable | Categoría | Cuerpo sugerido |
| --- | --- | --- |
| `WHATSAPP_PLANTILLA_CONFIRMACION` | Utilidad | ¡Listo, {{1}}! Tu cita de {{2}} con {{3}} quedó para el {{4}}. Total: {{5}}. Gestiónala aquí: {{6}} |
| `WHATSAPP_PLANTILLA_RECORDATORIO` | Utilidad | Hola {{1}}, te esperamos {{2}}: {{3}} el {{4}}. Confirma, reprograma o cancela: {{5}} |
| `WHATSAPP_PLANTILLA_CANCELACION` | Utilidad | {{1}}, cancelamos tu cita del {{2}}. Reserva cuando quieras: {{3}} |
| `WHATSAPP_PLANTILLA_PROMOCION` | Marketing | ¡{{1}}, te extrañamos! Hace {{2}} días no te vemos y tienes {{3}} puntos. Reserva: {{4}} · Para no recibir más promociones: {{5}} |

Si una variable queda vacía, ese mensaje se envía como texto libre, que solo llega a quien te escribió en las últimas 24 h.

## 6. Medidas de seguridad implementadas

| Riesgo | Control |
| --- | --- |
| Robo de la base de datos | El código se guarda como HMAC-SHA256 con una pimienta fuera de la base. El historial de mensajes no lo contiene. |
| Fuerza bruta del código | 3 intentos por código, vigencia de 10 minutos, un solo uso, y cada código nuevo anula el anterior. Comparación en tiempo constante. |
| Abuso que genera costos (bombeo de mensajes) | Límites por celular (5/h) y por IP (15/h), tope diario global y lista de países permitidos. |
| Filtración del token | Solo en variables de entorno, nunca en logs ni en reportes de error (`sensitive_variables`). `appsecret_proof` opcional. Token de usuario del sistema con permisos mínimos. |
| Webhooks falsificados | Firma HMAC-SHA256 con la clave secreta de la app sobre el cuerpo crudo, comparación en tiempo constante, cuerpo máximo de 1 MB. |
| Datos personales en logs | Teléfonos enmascarados (`+5730****233`). No se registra el contenido de los mensajes entrantes. |
| Caídas de Meta | Reintentos con espera exponencial solo ante errores transitorios. Los límites (429) no se reintentan en caliente. Si el envío falla, la reserva no se cae y se muestra un mensaje claro. |
| Mal despliegue | `python manage.py check --deploy` falla si faltan credenciales o si `SITIO_URL` no es HTTPS. |

**Rotación del token:** si sospechas una filtración, revoca el token en Configuración del negocio → Usuarios del sistema, genera uno nuevo, actualiza `WHATSAPP_TOKEN` y reinicia la aplicación. Haz lo mismo con la clave secreta de la app (App → Configuración → Básica → Restablecer).

# Navaja & Cuero — App de barbería (Django + HTMX + Alpine + Tailwind)

Aplicación web completa para una barbería: reserva del cliente 24/7 en 4 pasos con disponibilidad en tiempo real,
recordatorios por WhatsApp, historial y preferencias del cliente, puntos, y un panel interno con agenda por barbero,
caja diaria, inventario, comisiones, marketing de inactivos y reportes.

## 1. Ejecutar en tu computador (5 minutos)

Requisitos: **Python 3.11 o superior**. (Node solo si vas a cambiar estilos; ver sección 4.)

```bash
# 1) Entra a la carpeta del proyecto
cd barberia

# 2) Crea y activa un entorno virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3) Instala dependencias
pip install -r requirements.txt

# 4) Crea la base de datos y carga datos de demostración
python manage.py migrate
python manage.py seed_demo

# 5) Arranca el servidor
python manage.py runserver
```

Abre:

| Qué | URL | Acceso |
| --- | --- | --- |
| Web del cliente | http://127.0.0.1:8000/ | Reserva sin cuenta; el código de verificación aparece en pantalla (modo desarrollo) y en la terminal |
| Panel del equipo | http://127.0.0.1:8000/panel/ | `admin` / `admin12345` · `recepcion` / `recepcion123` · `andres` / `barbero123` |
| Configuración (Django Admin) | http://127.0.0.1:8000/admin/ | `admin` / `admin12345` |

Cliente demo para "Mis citas": celular **300 123 4567**.

Para recargar los datos de prueba desde cero: `python manage.py seed_demo --reset`.
Para ejecutar las pruebas automáticas: `python manage.py test`.

## 2. Estructura

```
barberia/
├── config/                 # settings.py (reglas del negocio en BARBERIA = {...}), urls
├── core/
│   ├── models.py           # Servicio, Barbero, Horario, Bloqueo, Cliente, Cita, Producto, Caja…
│   ├── disponibilidad.py   # cálculo de horas libres, retención de cupo, creación segura de citas
│   ├── operaciones.py      # cobros, puntos, inventario, comisiones, reportes
│   ├── notificaciones.py   # mensajes WhatsApp (o consola en desarrollo)
│   ├── otp.py              # código de 6 dígitos por WhatsApp
│   ├── roles.py            # admin / recepcion / barbero
│   ├── views_cliente.py    # web pública y reserva
│   ├── views_panel.py      # panel interno
│   ├── management/commands # seed_demo, enviar_recordatorios, alertar_inactivos
│   └── tests.py
├── templates/cliente/      # tema oscuro, mobile-first
├── templates/panel/        # tema claro, escritorio/tablet
├── templates/componentes/  # head, insignias de estado, avatar, mensajes
├── static/css/tailwind.css # CSS compilado (ya incluido)
├── static/vendor/          # htmx, alpine, echarts (sin depender de CDN)
├── tailwind.config.js      # tokens de color/tipografía de la guía de estilo
└── frontend/entrada.css
```

## 3. Cómo funciona lo importante

- **Disponibilidad**: el servidor calcula las horas libres (turnos − citas − bloqueos − cupos retenidos por otros).
  El selector se refresca cada 20 s con HTMX; si alguien toma tu hora, desaparece y se te avisa.
- **Sin dobles reservas**: al elegir hora se retiene el cupo 10 min; al confirmar se valida otra vez dentro de una
  transacción que bloquea al barbero (`select_for_update`).
- **"Cualquier barbero"**: une los horarios y asigna al barbero con menos citas ese día.
- **Roles**: superusuario o grupo `Admin` (todo), grupo `Recepcion` (agenda, caja, clientes, inventario),
  usuario enlazado a un Barbero (solo su agenda, sus clientes, registrar consumo y sus comisiones).
  Crea usuarios y asigna grupos o barberos en `/admin/`.
- **Puntos**: 1 punto por cada $1.000 pagados + 50 de bienvenida (ajusta en `config/settings.py`).
- **Reglas del negocio** (anticipación mínima, minutos de retención, horas de cancelación, etc.) en `BARBERIA = {...}`.

## 4. Cambiar estilos (Tailwind)

El CSS ya viene compilado. Si agregas clases nuevas en las plantillas, recompila:

```bash
npm install          # una sola vez
npm run dev:css      # deja corriendo mientras editas (o npm run build:css para compilar una vez)
```

Alternativa sin Node, solo para prototipar: pon `TAILWIND_CDN=1` en `.env` (usa el CDN de Tailwind).

## 5. Recordatorios y mensajes automáticos

```bash
python manage.py enviar_recordatorios          # cada 15 min: recordatorios 24 h y 2 h antes
python manage.py alertar_inactivos --dias 45   # 1 vez al día: reactivar clientes inactivos (--simular para probar)
```

- Linux/macOS: agrégalos a `crontab -e`, por ejemplo `*/15 * * * * cd /ruta/barberia && .venv/bin/python manage.py enviar_recordatorios`
- Windows: Programador de tareas con el mismo comando.
- Si más adelante usas Celery o Django-Q2, llama a los mismos comandos desde una tarea periódica.

Por defecto los mensajes se imprimen en la terminal (`MENSAJES_BACKEND=consola`). Para enviar por WhatsApp de verdad
(códigos de verificación, confirmaciones y recordatorios) sigue **`docs/WHATSAPP.md`**:

```bash
python manage.py whatsapp --verificar
python manage.py whatsapp --crear-plantilla-otp
python manage.py whatsapp --probar 3001234567
```

## 6. Protección de datos y cumplimiento legal (Colombia)

Implementado según la Ley 1581 de 2012, el Decreto 1074 de 2015, la Ley 2300 de 2023 y la Ley 1480 de 2011.
Antes de lanzar revisa **`legal/CHECKLIST_LANZAMIENTO.md`**: hay tareas que dependen del negocio, como contratos,
el RNBD y la capacitación del personal.

| Requisito | Dónde está |
| --- | --- |
| Política de tratamiento con el contenido mínimo legal | `/legal/privacidad/` · `templates/legal/privacidad.html` |
| Aviso de privacidad al recolectar datos | Paso 4 de la reserva y modal «Nueva cita» del panel |
| Autorización previa, expresa e informada, **sin casillas premarcadas** y con prueba (fecha, IP, texto, versión, canal) | `core/privacidad.py` · modelo `Consentimiento` |
| Datos sensibles (fotos) facultativos y separados | Casilla propia; si se revoca, las fotos se borran |
| Menores de edad | Declaración de mayoría de edad; no se piden datos ni fotos de menores |
| Consultas (10 días hábiles) y reclamos (15) con prórroga, leyenda «reclamo en trámite» y desistimiento | `/legal/mis-derechos/` y panel → Datos personales (festivos de Colombia incluidos) |
| Acceso, portabilidad, revocatoria y supresión de autoservicio | Perfil → Mis datos (descargar JSON, autorizaciones, eliminar cuenta) |
| Supresión que conserva los soportes contables anonimizados | `privacidad.anonimizar_cliente` |
| Publicidad solo con autorización, en horario legal, máximo 1 por semana y con enlace de baja | `privacidad.en_horario_publicidad`, `/legal/baja/<token>/` |
| Nueva aceptación cuando cambia la versión de la política | `POLITICA_VERSION` en settings |
| Conservación limitada | `python manage.py depurar_datos` (diario) |
| Seguridad: fotos privadas, CSP, HTTPS/HSTS, límites de intentos, bitácora de accesos, fuentes locales | `core/middleware.py`, `core/archivos.py`, `RegistroAcceso` |
| Términos y condiciones, identificación del proveedor y enlace a la SIC | `/legal/terminos/` y pie de página |
| No se puede desplegar sin los datos del responsable | `python manage.py check --deploy` (barberia.E001) |

Documentos internos en `legal/`: manual interno con compromiso de confidencialidad, contrato de transmisión con
encargados y formato de autorización de imagen para publicidad.

## 7. Pasar a producción (resumen)

1. `.env`: `DJANGO_DEBUG=0`, una `DJANGO_SECRET_KEY` nueva, `DJANGO_ALLOWED_HOSTS=tudominio.com`, `SITIO_URL=https://tudominio.com`.
2. PostgreSQL: `pip install "psycopg[binary]"` y completa las variables `POSTGRES_*`.
3. `pip install gunicorn whitenoise`, `python manage.py collectstatic`, servir con `gunicorn config.wsgi`.
4. Programa `enviar_recordatorios` (cada 15 min), `alertar_inactivos` (diario, 10:00 a. m.) y `depurar_datos` (diario).
5. Completa los datos del responsable en `.env` y ejecuta `python manage.py check --deploy` hasta que no muestre errores.
6. Opcional: tiempo real instantáneo con Django Channels (WebSockets) en lugar del refresco cada 20 s.

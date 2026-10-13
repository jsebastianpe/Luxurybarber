# Lista de verificación legal antes de lanzar

Marco: Ley 1581 de 2012, Decreto 1074 de 2015 (caps. 25 y 26), Ley 1480 de 2011, Ley 2300 de 2023, Ley 527 de 1999.

> Este software implementa los controles técnicos. Las tareas marcadas como **[negocio]** dependen del dueño y
> no se pueden resolver con código. Antes de lanzar, pide a un abogado que revise los textos con los datos
> reales de tu negocio.

## 1. Datos del responsable (bloquean el despliegue)
- [ ] `RESP_RAZON_SOCIAL`, `RESP_TIPO_ID`, `RESP_NUMERO_ID`, `RESP_DIRECCION`, `RESP_EMAIL_DATOS`, `RESP_TELEFONO` en `.env`.
      `python manage.py check --deploy` falla (barberia.E001) mientras falten.
- [ ] `RESP_MATRICULA` (matrícula mercantil), si existe.
- [ ] Crear el buzón `RESP_EMAIL_DATOS` y asignar a la persona que lo revisa al menos cada 2 días hábiles. **[negocio]**
- [ ] `RESP_AREA`: nombre del cargo o persona designada como responsable de protección de datos. **[negocio]**

## 2. Encargados y transmisiones
- [ ] `ENCARGADO_HOSTING` y `ENCARGADO_HOSTING_PAIS` con tu proveedor real (aparecen en la política).
- [ ] Firmar un **contrato de transmisión** con cada encargado (plantilla: `CONTRATO_TRANSMISION.md`) o aceptar
      sus términos de procesamiento de datos (DPA) si cumplen ese contenido: hosting, WhatsApp/Meta, correo. **[negocio]**
- [ ] Si algún proveedor guarda datos en un país que **no** está en la lista de la SIC (Circular Externa 005 de 2017
      y sus actualizaciones), pide la declaración de conformidad o usa otro proveedor. **[negocio]**

## 3. Registro Nacional de Bases de Datos (RNBD)
- [ ] Solo están obligadas las **sociedades y entidades sin ánimo de lucro con activos totales superiores a
      100.000 UVT** y las personas jurídicas de naturaleza pública (Decreto 090 de 2018). Las personas naturales
      no están obligadas. Si tu empresa supera el umbral, inscribe la base «Clientes» (y «Empleados») en
      rnbd.sic.gov.co dentro del plazo y actualízala cada año. **[negocio]**

## 4. Mensajería
- [ ] WhatsApp Business: plantillas aprobadas por Meta para el código, la confirmación y los recordatorios.
      La plantilla de promociones debe incluir el enlace de baja que agrega el sistema.
- [ ] Programar `enviar_recordatorios` cada 15 min, `alertar_inactivos` una vez al día en horario permitido
      (ej. 10:00 a. m.) y `depurar_datos` una vez al día (ej. 3:00 a. m.).
- [ ] Nunca enviar publicidad manual fuera del sistema a clientes sin `acepta_marketing` (Ley 2300 de 2023, art. 5). **[negocio]**

## 5. Seguridad
- [ ] `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` nueva y larga, HTTPS con certificado válido, `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS`.
- [ ] PostgreSQL con contraseña fuerte y sin acceso público. Copias de seguridad diarias **cifradas** y prueba de restauración mensual.
- [ ] Carpeta `media/` fuera de la raíz pública del servidor web (las fotos se sirven solo por la aplicación).
- [ ] Cambiar las contraseñas de demostración; un usuario personal por empleado; nada de cuentas compartidas.
- [ ] Borrar los datos de demostración: no ejecutes `seed_demo` en producción.
- [ ] Redis (`REDIS_URL`) si usas más de un proceso, para que los límites de intentos se compartan.

## 6. Personal
- [ ] Cada empleado con acceso al panel firma la cláusula de confidencialidad (`MANUAL_INTERNO.md`, anexo A). **[negocio]**
- [ ] Capacitación de 30 minutos sobre el manual interno, al ingresar y cada año. Guarda la constancia. **[negocio]**
- [ ] Autorización de los barberos para usar su nombre y foto en el sitio (`FORMATO_AUTORIZACION_IMAGEN.md`). **[negocio]**

## 7. Consumidor (Ley 1480)
- [ ] Precios publicados = precios cobrados, con impuestos incluidos.
- [ ] Revisar los valores de `BARBERIA` en `config/settings.py` (cancelación, tolerancia, garantía, medios de pago, horario):
      se publican en los términos y condiciones.
- [ ] El enlace a la SIC queda visible en el pie de página (ya implementado).

## 8. Cada vez que cambies la política o los términos
- [ ] Sube `POLITICA_VERSION` o `TERMINOS_VERSION` y `POLITICA_VIGENCIA` en `config/settings.py`.
      Los clientes verán la nueva versión y deberán aceptarla al ingresar.
- [ ] Si cambian las **finalidades**, además avisa por WhatsApp o correo antes de aplicar el cambio (Decreto 1074, art. 2.2.2.25.3.1).

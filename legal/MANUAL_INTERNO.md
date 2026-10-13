# Manual interno de políticas y procedimientos de protección de datos personales

Exigido por el artículo 17, literal k, de la Ley 1581 de 2012. Aplica a todo el personal con acceso a datos de
clientes o empleados: dueño, recepción, barberos y proveedores.

Versión 1.0 · Responsable: [RAZÓN SOCIAL] · Persona encargada de protección de datos: [NOMBRE Y CARGO]

## 1. Bases de datos que manejamos

| Base | Contenido | Dónde está | Quién accede |
| --- | --- | --- | --- |
| Clientes | Nombre, celular, correo, citas, pagos, puntos, preferencias, notas, fotos (si autorizó) | Sistema de reservas | Admin y recepción: todos los clientes. Barbero: solo los clientes que atiende |
| Autorizaciones | Prueba de cada autorización y revocatoria | Sistema (solo lectura) | Admin |
| Solicitudes de habeas data | Consultas, reclamos y respuestas | Sistema → Datos personales | Admin |
| Empleados | Datos laborales y de nómina | [Indicar: carpeta física, software contable…] | Dueño / contador |

## 2. Reglas para todo el equipo
1. Solo consulta los datos de un cliente cuando lo necesites para atenderlo. El sistema registra cada consulta.
2. No copies datos de clientes a tu celular personal, chats personales, hojas de cálculo ni fotos de pantalla.
3. No escribas datos de salud ni opiniones personales en las notas. El cliente puede pedir ver todo lo que hay en su ficha.
4. No tomes ni guardes fotos de un cliente sin que la ficha diga «Fotos: autorizadas». **Nunca fotografíes a menores de edad.**
5. Nunca publiques fotos de clientes en redes sociales sin el formato `FORMATO_AUTORIZACION_IMAGEN.md` firmado.
6. No compartas tu usuario ni tu contraseña. Cierra sesión en equipos compartidos.
7. No envíes promociones desde tu WhatsApp personal. La publicidad solo sale desde el sistema, que verifica autorización, horario y frecuencia (Ley 2300 de 2023).

## 3. Registrar a un cliente en el local o por teléfono
1. Lee el aviso de privacidad que aparece en «Nueva cita».
2. Pregunta: «¿Nos autorizas a tratar tus datos para agendar y enviarte los recordatorios?». Si dice que no, atiéndelo sin registrarlo.
3. Marca la casilla de autorización solo si dijo que sí. Queda registrado a tu nombre como prueba.
4. Pregunta **por separado** si quiere recibir promociones. Por defecto, no.

## 4. Atender consultas y reclamos (panel → Datos personales)
| Paso | Plazo |
| --- | --- |
| Revisar solicitudes nuevas | Cada 2 días hábiles como máximo |
| Verificar identidad (celular registrado y documento; poder o registro civil si es un tercero) | Al recibirla |
| Pedir información si el reclamo está incompleto | Dentro de 5 días desde que se recibe |
| Leyenda «reclamo en trámite» | El sistema la muestra en la ficha automáticamente |
| Responder una consulta | 10 días hábiles (prórroga: 5, informando el motivo) |
| Responder un reclamo | 15 días hábiles (prórroga: 8, informando el motivo) |
| Desistimiento si no completa el reclamo | 2 meses después de pedir la información (el sistema lo marca solo) |

En una respuesta de supresión, explica qué se borró y qué se conserva por obligación legal, por ejemplo los soportes contables sin datos personales.

## 5. Conservación y eliminación
El comando `depurar_datos` aplica cada día los plazos de la política, sección 13. No borres datos a mano fuera de los procedimientos, porque se pierde la trazabilidad.

## 6. Incidentes de seguridad
Ejemplos: robo de un celular con sesión abierta, acceso no autorizado, envío de datos a la persona equivocada o pérdida de copias de seguridad.
1. Avisa al responsable de protección de datos **el mismo día**.
2. Contén el incidente: cambia contraseñas, cierra sesiones y revoca tokens.
3. Documenta qué pasó, qué datos se afectaron, cuántos titulares y qué se hizo.
4. Reporta el incidente a la SIC por el Registro Nacional de Bases de Datos o por el canal que indique la SIC, dentro de los 15 días hábiles siguientes a detectarlo, según sus instrucciones vigentes.
5. Avisa a los titulares afectados cuando el incidente pueda causarles daño.

## 7. Proveedores (encargados)
Ningún proveedor recibe datos sin un contrato de transmisión (`CONTRATO_TRANSMISION.md`) o sin aceptar condiciones equivalentes. Revisa la lista de proveedores una vez al año.

## 8. Capacitación y revisión
Capacitación al ingresar y cada año, con constancia firmada. Revisa este manual cada año o cuando cambie la ley.

---
### Anexo A. Compromiso de confidencialidad del personal

Yo, ______________________, identificado con C.C. __________, en mi calidad de __________ de [RAZÓN SOCIAL], declaro:

1. Conozco la Política de Tratamiento de Datos Personales y este manual.
2. Usaré los datos de clientes solo para las funciones de mi cargo.
3. Guardaré reserva sobre ellos incluso después de terminar mi relación laboral o contractual (Ley 1581 de 2012, art. 4 lit. h).

Sé que el incumplimiento puede acarrear sanciones disciplinarias y legales.

Firma: ______________________ Fecha: ____/____/______

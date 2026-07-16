# Guia funcional

## Perfiles

### Clinica

Puede gestionar clientes y mascotas, registrar prestaciones, consultar
historiales, ejecutar reindexaciones y reconstruir avisos.

### Personal

Dispone de acceso global de solo lectura. Puede utilizar el analisis RAG de
historiales, pero no modificar registros.

### Propietario

Solo consulta sus mascotas, planes y pagos. Puede preguntar al asistente por
sus propios animales y utilizar el modo de informacion general. No puede
recuperar historiales de otros pacientes ni notas internas.

## Asistente de informacion general

Disponible para todos los perfiles. Utiliza exclusivamente documentos
cargados en `data/rag` y devuelve fuentes externas cuando existen.

## Consulta de una mascota

Disponible para los perfiles de negocio:

1. Abrir **Asistente**.
2. Seleccionar **Datos de la mascota**.
3. Elegir una mascota autorizada.
4. Preguntar por prestaciones, pagos, vacunas, antecedentes o avisos.

El propietario solo ve eventos marcados como visibles. La clinica y el personal
pueden usar el mismo modo para revisar un paciente concreto.

## Estado de pago

La ficha del paciente muestra si el plan esta pagado o se abona a plazos. En
este ultimo caso se indican las cuotas pagadas, hasta un maximo de 12, el total
abonado y el importe pendiente. Solo la clinica puede editar estos datos.

## Analisis de historiales clinicos

Disponible para clinica y personal:

1. Abrir **Asistente**.
2. Seleccionar **Historiales clinicos**.
3. Preguntar por sintomas, razas, diagnosticos o recurrencias.
4. Revisar las etiquetas de fuente bajo la respuesta.
5. Abrir la ficha del paciente desde la etiqueta correspondiente.

Consultas de ejemplo:

```text
Que pacientes han tenido otitis recurrente?
Aparecen problemas respiratorios repetidos en razas braquicefalicas?
Que casos articulares se repiten y en que razas?
Hay gatos con seguimiento renal o perdida de peso?
```

La respuesta se limita a los fragmentos recuperados. No debe interpretarse como
un estudio estadistico ni como una conclusion diagnostica.

## Avisos preventivos

En la ficha de una mascota pueden aparecer dos textos:

- Aviso base: creado por una regla auditable.
- Explicacion RAG: resumen generado con historiales y documentos relacionados.

Las fuentes que justifican la explicacion aparecen como etiquetas. Si no existe
contexto suficiente, solo se muestra el aviso base.

## Actualizacion de los datos vectoriales

Despues de cambiar historiales:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api python -m app.rag.ingest
```

Para volver a generar las explicaciones de los avisos:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api python -m app.scripts.enrich_alerts
```

## Gestion integral de planes (version 0.5.0)

El perfil de clinica gestiona el plan desde la ficha de cada mascota.

### Asignar un plan

Cuando no existe una suscripcion activa o programada, aparece el boton
**Asignar plan**. La aplicacion solo ofrece planes de la especie correspondiente.
Se debe indicar la fecha de inicio y si el pago se realiza completo o a plazos.

Al confirmar, la API crea la suscripcion y genera automaticamente sus
prestaciones. Los servicios periodicos respetan la frecuencia del catalogo y
los usos multiples se distribuyen durante el periodo anual.

### Cambiar de plan

El cambio se aplica de forma inmediata. El plan anterior queda cancelado, pero
sus prestaciones realizadas y sus movimientos de pago permanecen en la base de
datos. Las prestaciones que aun no se habian utilizado quedan anuladas.

### Cancelar un plan

La baja exige fecha y motivo. Se trata de una baja logica: no elimina la
suscripcion ni su historial y permite justificar posteriormente que ocurrio.

### Renovar

La clinica puede programar el siguiente periodo antes de que venza el actual.
La nueva suscripcion comienza, por defecto, el dia posterior a la fecha de fin y
se muestra como **Programada** hasta que llegue su fecha de inicio.

El propietario puede solicitar la renovacion durante los ultimos 90 dias. La
clinica revisa las solicitudes desde **Planes LifeCare** y puede aprobarlas o
rechazarlas.

### Vencimientos

La pantalla de planes muestra las suscripciones que vencen en los proximos 45
dias, su estado de pago y el importe que queda pendiente. El listado enlaza con
la ficha de la mascota para realizar la gestion.

## Gestion de avisos preventivos (version 0.6.0)

Clinica y personal disponen de la opcion **Avisos preventivos**. La pantalla
muestra estadisticas y permite filtrar por estado, severidad, especie, categoria
o nombre de mascota.

Cada aviso contiene:

- Regla y version aplicada.
- Evidencia que activo la condicion.
- Fuente documental de la regla.
- Explicacion generada mediante RAG cuando existe contexto suficiente.
- Fecha de la ultima evaluacion.
- Numero de veces que la condicion ha reaparecido.
- Historial de cambios de estado.

Solo la clinica puede realizar acciones:

- **Revisar:** deja constancia de que el caso ha sido valorado.
- **Resolver:** cierra el aviso con un motivo obligatorio.
- **Descartar:** indica que la regla no resulta aplicable al caso.
- **Reabrir:** devuelve un aviso cerrado a estado nuevo.

El boton **Recalcular y enriquecer** revisa todas las mascotas y puede tardar
varios minutos. **Solo recalcular** ejecuta las reglas sin llamar al LLM.

### Registrar un evento clinico

Desde la ficha de la mascota, el perfil de clinica puede pulsar **Anadir
evento** e indicar fecha, tipo, descripcion, diagnostico ya registrado,
tratamiento, peso y visibilidad para el propietario.

El guardado no espera a que termine el modelo. La reindexacion y el recalculo de
avisos se realizan en segundo plano. La ficha puede recargarse unos segundos
despues para consultar el resultado.

## Calidad del RAG (version 0.7.0)

Los perfiles de clinica y personal disponen de la opcion **Calidad de VetIA**.

La pantalla permite comprobar:

- Si Qdrant esta disponible.
- Cuantos vectores y documentos hay cargados.
- Que categorias cubre la base documental.
- Cuando se realizo la ultima ingesta.
- Resultado de la ultima evaluacion.

El perfil de clinica puede ejecutar una evaluacion. El modo **Recuperacion** es el recomendado para comprobaciones habituales. La opcion **Incluir generacion** consulta tambien a Ollama y tarda mas.

En el chat, las fuentes aparecen identificadas como `F0`, `F1`, etc. La etiqueta de confianza se refiere a la recuperacion del contexto, no a una certeza diagnostica.

## Paneles de control (version 0.8.0)

La pagina **Resumen** adapta su contenido al perfil autenticado.

### Clinica y personal

- Utiliza los filtros de periodo, especie y plan para acotar los indicadores.
- Pulsa una tarjeta para abrir la pantalla operativa relacionada.
- Revisa la agenda para localizar cuotas, servicios, planes o avisos que requieren atencion.
- Usa **Exportar CSV** para descargar exactamente el mismo alcance mostrado.

El personal de solo lectura puede consultar los paneles y exportarlos, pero no puede modificar datos.

### Propietario

Cada mascota dispone de una tarjeta con plan, cumplimiento, saldo pendiente,
proxima cuota, servicios y avisos. Los botones permiten abrir la ficha o iniciar
una pregunta privada en el asistente.

Los filtros nunca permiten visualizar mascotas de otros propietarios porque el
alcance se impone en FastAPI antes de calcular los indicadores.


## Integracion Wakyma simulada (version 0.9.0)

Clinica y personal pueden abrir **Integracion Wakyma**. El personal solo puede validar y consultar el historial. La clinica puede ejecutar la importacion.

El flujo recomendado es:

1. Descargar la plantilla JSON o CSV.
2. Completarla con datos ficticios.
3. Validarla.
4. Corregir las filas rechazadas.
5. Importarla.
6. Descargar las credenciales temporales de propietarios nuevos.

El detalle de cada lote muestra la accion prevista o realizada. `create` indica un registro nuevo y `update` uno localizado por `external_id`. La validacion nunca modifica clientes, mascotas ni historiales.

## Seguridad y auditoria (version 0.10.0)

### Primer acceso con una contrasena temporal

Los propietarios creados desde **Clientes** o importados desde Wakyma deben cambiar la contrasena temporal antes de utilizar la aplicacion:

1. Iniciar sesion con el correo y la contrasena entregada por la clinica.
2. La aplicacion abre automaticamente **Cambiar contrasena**.
3. Introducir la contrasena actual y una nueva que cumpla la politica.
4. La nueva sesion sustituye a las anteriores.

### Gestionar sesiones

Todos los perfiles pueden abrir **Seguridad** para ver fecha, caducidad, IP aproximada y navegador de sus sesiones. Una sesion que no se reconozca puede revocarse. El cambio de contrasena revoca todas las sesiones anteriores.

### Revisar la auditoria

`clinic` y `staff` disponen de **Auditoria**. Se puede filtrar por actor, accion, entidad, resultado y periodo. El detalle muestra los campos modificados, pero no duplica contrasenas, tokens ni texto clinico libre.

Solo `clinic` puede utilizar **Exportar CSV**. La exportacion respeta los filtros y esta limitada a 5.000 registros para evitar descargas sin control.

### Cuenta bloqueada

Tras varios intentos incorrectos aparece el estado de cuenta bloqueada temporalmente. El desbloqueo se produce al finalizar el periodo configurado. Esta medida no sustituye una futura recuperacion de contrasena por correo.


## Validacion formal del MVP (version 0.11.0)

Los perfiles `clinic` y `staff` pueden consultar **Validacion del MVP**. Solo
`clinic` puede iniciar una ejecucion. La pantalla muestra criterios de
aceptacion, pruebas, cobertura, exactitud de avisos, controles de seguridad,
recuperacion de VetIA y latencia de la API.

El informe se descarga en Markdown y cada ejecucion queda almacenada para poder
comparar versiones. La evaluacion automatica no sustituye la revision
veterinaria humana.


## Perfil tecnico

El usuario `technical@gamucare.local` dispone de un espacio separado con Calidad de VetIA, Validacion del MVP, Integracion Wakyma, Auditoria, Seguridad y Estado tecnico. No puede consultar la operacion diaria de clientes, mascotas, planes o pagos.

## Calidad de VetIA en 0.14.0

El perfil tecnico puede comprobar tres capas diferentes:

1. **Corpus**: documentos locales, fuentes externas descargadas y vectores.
2. **Recuperacion**: acierto, MRR, rechazo y latencia.
3. **Generacion**: respuesta final, citas y decision de uso del contexto.

Una consulta puede terminar con estas decisiones:

- `accepted`: VetIA dispone de evidencia suficiente.
- `out_of_scope`: la pregunta no es veterinaria y no se consulta Qdrant.
- `low_score`: hay textos parecidos, pero no superan el umbral.
- `no_evidence`: no se ha encontrado contenido util.

El top score representa similitud del fragmento, no porcentaje de certeza ni
probabilidad de diagnostico correcto.


## Mensajes de error y acceso en 0.15.0

Cuando una operacion falla, algunos mensajes muestran un identificador de
solicitud. Ese valor permite al perfil tecnico localizar la peticion en los logs
y la auditoria sin mostrar trazas internas al usuario.

Si un perfil abre una URL para la que no tiene permiso, la aplicacion muestra
**Acceso no permitido** y permite volver al inicio. Esta pantalla no sustituye
la validacion del backend: FastAPI tambien responde con `403`.

# Decisiones tecnicas

## PostgreSQL frente a MongoDB

El dominio contiene relaciones estables entre usuarios, propietarios, mascotas,
planes, suscripciones, servicios e historiales. PostgreSQL aporta integridad
referencial, transacciones y consultas agregadas.

## Ollama frente a vLLM

Ollama simplifica la ejecucion local en Docker Desktop y el uso de modelos
cuantizados en una GTX 1060 de 6 GB. vLLM esta orientado a mayor concurrencia y
suele requerir mas memoria de GPU.

## RAG directo

Se utilizan clientes directos de Ollama y Qdrant. Esto reduce capas, facilita la
depuracion y permite explicar cada paso durante la defensa.

## Una coleccion con tipos filtrados

Los documentos y los historiales comparten modelo de embedding y coleccion,
pero cada punto incluye `content_type`. Qdrant aplica filtros obligatorios segun
el alcance solicitado. Esta solucion simplifica el MVP sin mezclar permisos.

## Historias clinicas sin datos de propietario

Se vectorizan el nombre de la mascota, especie, raza, edad, antecedentes y
eventos. No se incorporan correo, telefono, direccion ni nombre del propietario.
Aunque los datos son ficticios, esta separacion muestra una practica coherente
con minimizacion de datos.

## Reglas antes que diagnostico generativo

Las alertas nacen de condiciones deterministas. RAG y Ollama solo explican el
aviso y aportan referencias. El modelo no puede crear por si mismo una alerta ni
confirmar una enfermedad.

## Datos recurrentes ficticios

Se anaden eventos repetidos para demostrar busqueda de patrones. No representan
prevalencias reales ni asociaciones cientificas. El script es idempotente y usa
identificadores `RAG-DEMO-*` para distinguirlos.

## Roles simplificados

El MVP utiliza `clinic`, `staff` y `owner`. `staff` representa al personal que
necesita consultar historiales, incluido el veterinario, pero no modificar datos.
La autorizacion se aplica en FastAPI y no solo ocultando controles en React.

## Datos transaccionales fuera del vector store

El historial se vectoriza para permitir busqueda semantica, pero los pagos y el
estado actual del plan se consultan siempre en PostgreSQL. De esta forma una
respuesta no depende de una reindexacion para mostrar cantidades actualizadas.
El prompt de la mascota combina esos datos estructurados con los eventos
recuperados desde Qdrant.

## Aislamiento del historial del propietario

El alcance `pet` aplica dos comprobaciones. FastAPI valida la relacion entre el
usuario y la mascota, y Qdrant filtra los puntos por `pet_id` y
`visible_to_owner`. La doble barrera reduce el riesgo de que una consulta
semantica recupere informacion de otro paciente o una nota interna.

## Ciclo de vida auditable para los avisos

Cada mascota mantiene como maximo un aviso por regla. Se actualiza la evidencia
en lugar de insertar duplicados. Las acciones del usuario y los cierres
automaticos se guardan en una tabla historica independiente. Esta decision
permite explicar que ocurrio incluso si el estado actual cambia.

## Reindexacion individual en segundo plano

Los cambios cotidianos no reconstruyen toda la coleccion vectorial. Se sustituyen
solo los puntos de la mascota afectada y despues se recalculan sus reglas. El
flujo es asincrono para que guardar un evento no quede bloqueado por la latencia
del modelo local.

La decision completa se documenta en
`docs/architecture/decisions/ADR-005-preventive-alert-engine.md`.


## Frontera de integracion Wakyma

Los formatos JSON y CSV se transforman primero en registros normalizados. La logica de actualizacion no depende del transporte y utiliza `external_id` como clave idempotente. No se inventa una API comercial: el conector se presenta expresamente como simulado y sustituible.

La decision completa se documenta en `docs/architecture/decisions/ADR-008-wakyma-adapter-boundary.md`.

## Sesiones cortas, renovables y revocables

El frontend utiliza un access token de corta duracion en `sessionStorage`. La continuidad de la sesion depende de un refresh token HttpOnly que se rota en cada uso y cuyo valor completo nunca se guarda en PostgreSQL. El cambio de contrasena incrementa `token_version`, por lo que invalida todos los access tokens anteriores.

## Auditoria separada de los historiales clinicos

Los cambios relevantes se registran en `audit_logs`, pero las instantaneas pasan antes por un filtro de minimizacion. Las contrasenas y tokens se eliminan, los datos de contacto se ocultan y los textos clinicos libres no se duplican. La decision completa se documenta en `docs/architecture/decisions/ADR-009-session-security-and-audit.md`.

## Evaluacion formal versionada del MVP

La calidad se evalua mediante una suite interna con datasets JSON versionados,
pytest, cobertura, casos del motor preventivo, controles de seguridad,
recuperacion de VetIA y un benchmark corto. Cada ejecucion se almacena en
PostgreSQL y genera un informe descargable. La decision completa se documenta
en `docs/architecture/decisions/ADR-010-formal-mvp-evaluation.md`.


## ADR-011 - Observabilidad y backups locales

Se adopta Prometheus, Grafana, Alertmanager, PostgreSQL Exporter y Blackbox
Exporter dentro de un perfil Docker Compose opcional. Los datos se protegen con
`pg_dump`, snapshots de Qdrant y un manifiesto SHA-256. Se descarta copiar
volumenes en caliente y se evita incluir modelos de Ollama por ser reproducibles.


## Separacion del perfil tecnico

Desde la version 0.13.0 se utiliza `technical` para las funciones de calidad, integracion, auditoria, seguridad y observabilidad. `clinic`, `staff` y `owner` quedan limitados a la operacion de negocio. La autorizacion se aplica tanto en la interfaz como en FastAPI.

## ADR-013 - Filtro de dominio y gobierno documental

Desde la version 0.14.0, las consultas ajenas al ambito veterinario se rechazan
antes de generar embeddings. Los documentos oficiales externos se describen en
un manifiesto versionado y se descargan desde el organismo de origen con hash y
metadatos de trazabilidad. Consulte
`docs/architecture/decisions/ADR-013-domain-gate-and-source-governance.md`.


## Cierre funcional y errores trazables

Desde la version 0.15.0 se conserva `detail` en las respuestas HTTP para no
romper los consumidores existentes y se anaden `error_code` y `request_id`. Los
errores internos se registran, pero nunca se devuelven al navegador. La matriz
de permisos y la recuperacion de Qdrant/Ollama se validan mediante scripts
repetibles. La decision completa se recoge en ADR-014.


## Candidato de entrega y congelacion del alcance

Desde v0.16.0-rc1 no se incorporan nuevos modulos de negocio. El entorno demo
puede reconstruirse sin eliminar los modelos locales y las evidencias se generan
como artefactos fechados con hashes. AWS queda fuera del alcance. La decision
completa se documenta en `ADR-015-release-candidate-and-scope-freeze.md`.

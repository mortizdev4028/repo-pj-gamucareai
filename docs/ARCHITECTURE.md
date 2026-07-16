# Arquitectura tecnica

## Vista general

```text
Navegador
   |
   v
Nginx + React
   |
   v
FastAPI
   |-- PostgreSQL
   |-- Qdrant
   |-- Ollama
   |-- Motor de reglas preventivas
   `-- Adaptador Wakyma simulado

FastAPI /metrics ----> Prometheus ----> Grafana
Qdrant /metrics ----/      |
PostgreSQL Exporter -------/
Blackbox Exporter ---------/
                            `----> Alertmanager

Backup local: pg_dump + snapshot Qdrant + manifest SHA-256
```

## Tipos de conocimiento en Qdrant

La coleccion `gamucare_knowledge` contiene tres tipos de puntos:

- `reference_document`: fragmentos de documentos sobre vacunas, viajes y
  tramites.
- `clinical_profile`: resumen de especie, raza, edad, peso, alergias y
  antecedentes de una mascota.
- `clinical_event`: visita, prueba, diagnostico o seguimiento registrado en el
  historial ficticio.

Los datos de contacto del propietario no se vectorizan. Cada punto clinico
incluye metadatos como `pet_id`, nombre de la mascota, raza, especie, fecha y
tipo de evento.

## Control de acceso del RAG

El filtro no depende solo de la interfaz:

- `owner` puede consultar `reference_document` y utilizar el alcance `pet`
  sobre una mascota que pertenezca a su cuenta.
- En el alcance `pet`, Qdrant filtra por `pet_id` y por
  `visible_to_owner=true`; FastAPI vuelve a validar la propiedad antes de
  construir el prompt.
- `clinic` y `staff` pueden usar el alcance `clinical`, que recupera historiales
  de varios pacientes para localizar recurrencias.
- FastAPI devuelve `403` si un propietario intenta solicitar el alcance
  clinico global o consultar una mascota ajena.

## Flujo de RAG general

1. FastAPI valida al usuario y el alcance.
2. Ollama genera el embedding de la pregunta.
3. Qdrant filtra por `reference_document`.
4. Se eliminan resultados inferiores a `RAG_MIN_SCORE`.
5. Ollama responde solo con el contexto recuperado.
6. PostgreSQL guarda pregunta, respuesta, fuentes, modelo y latencia.

## Flujo de consulta de una mascota

1. El usuario selecciona una mascota.
2. FastAPI valida que el propietario tenga acceso a ella.
3. PostgreSQL aporta ficha, plan, pagos, prestaciones, avisos e historial
   autorizado.
4. Qdrant recupera solo fragmentos con el mismo `pet_id`.
5. Para propietarios se exige ademas `visible_to_owner=true`.
6. Ollama responde con ambos contextos sin crear diagnosticos nuevos.

El pago no se vectoriza porque es un dato transaccional que debe leerse siempre
desde PostgreSQL. El RAG se utiliza para localizar eventos relevantes del
historial, mientras que las cantidades y estados se incorporan directamente al
prompt desde la base relacional.

## Flujo de analisis clinico

1. El personal formula una consulta sobre raza, sintomas o recurrencias.
2. Qdrant recupera hasta `RAG_CLINICAL_TOP_K` fichas y eventos relacionados.
3. El prompt obliga a diferenciar hechos observados de posibles lineas de
   revision.
4. La respuesta indica que la muestra no representa prevalencia real.
5. Las fuentes enlazan con la ficha de la mascota para su comprobacion.

El sistema no calcula incidencia epidemiologica ni realiza diagnosticos. Es una
herramienta de busqueda semantica y resumen de historiales.

## Flujo de alertas preventivas

```text
PostgreSQL -> motor de reglas -> alerta determinista
                                   |
                                   v
                          consulta semantica
                                   |
                         Qdrant + Ollama
                                   |
                       explicacion y fuentes
```

La regla sigue siendo el origen del aviso. El RAG aporta contexto procedente de
historiales ficticios y documentos. Si Qdrant u Ollama no estan disponibles, la
alerta se conserva con su evidencia estructurada y sin explicacion generativa.

## Ingesta

`python -m app.rag.ingest` reconstruye la coleccion completa. Los embeddings se
generan por lotes para reducir el tiempo de carga. La reindexacion debe
ejecutarse despues de modificar historiales o documentos.

## Alcance de despliegue

La entrega se ejecuta en local mediante Docker Compose. PostgreSQL, Qdrant,
Ollama, FastAPI, Nginx y la monitorizacion se mantienen dentro del mismo
proyecto. Un despliegue externo no forma parte del alcance del MVP.

## Ciclo de vida de una suscripcion

La logica de negocio de los planes se encuentra en
`backend/app/services/subscriptions.py`. Los routers no calculan directamente
fechas, estados ni prestaciones.

Estados utilizados:

- `scheduled`: la fecha de inicio aun no ha llegado.
- `active`: plan vigente con mas de 45 dias restantes.
- `expiring`: plan vigente que finaliza en 45 dias o menos.
- `expired`: fecha de finalizacion superada.
- `cancelled`: baja registrada por la clinica.

La tabla `pet_plan_subscriptions` conserva el motivo y la fecha de cancelacion,
asi como la referencia a la suscripcion anterior cuando existe una renovacion.
Las solicitudes del propietario se almacenan en `renewal_requests` antes de que
la clinica cree el siguiente periodo.

La generacion de prestaciones es determinista. El LLM no participa en los
calculos de vigencia, pagos, renovaciones ni servicios incluidos.

## Calendario de pagos

La tabla `plan_installments` materializa cada cuota de una suscripcion. El
resumen almacenado en `pet_plan_subscriptions` se mantiene sincronizado para que
los paneles puedan calcular importes sin recorrer todo el calendario.

La generacion y actualizacion se realizan en
`backend/app/services/subscriptions.py`. Las fechas se reparten dentro de los
doce meses de vigencia y el ultimo importe absorbe cualquier diferencia de
redondeo. Una cancelacion conserva las cuotas pagadas y anula las pendientes.

## Evolucion del motor preventivo en 0.6.0

El catalogo de reglas vive en `backend/app/services/risk_catalog.py`. Cada
entrada incluye codigo estable, version, categoria, condiciones, severidad,
fuente y politica de resolucion automatica.

El motor admite cuatro familias de evidencia:

- Datos estructurados: especie, raza, edad y peso actual.
- Historial: terminos coincidentes, numero de episodios y ventana temporal.
- Tendencia de peso: comparacion de mediciones dentro de una ventana definida.
- Plan de salud: prestaciones vencidas por tipo y dias de retraso.

La restriccion unica `pet_id + rule_code` evita duplicados. Cuando cambia la
evidencia se actualiza el aviso existente y se invalida la explicacion anterior
para que el RAG la regenere. Si una condicion deja de cumplirse y la regla lo
permite, el aviso se resuelve automaticamente. Si vuelve a aparecer, se reabre
y aumenta `occurrence_count`.

La tabla `alert_status_history` conserva las transiciones manuales y
automaticas. Los estados cerrados son `resolved` y `dismissed`; un aviso
descartado no se reabre automaticamente porque representa una decision clinica
explicita.

## Actualizacion incremental de Qdrant

`app.rag.ingest.upsert_pet` elimina y vuelve a crear solo los puntos de una
mascota. Se ejecuta en segundo plano despues de cambios relevantes. La ingesta
completa sigue disponible para actualizaciones masivas de documentos o
migraciones.

```text
Cambio de mascota o evento
        |
        v
FastAPI BackgroundTask
        |
        +--> upsert_pet en Qdrant
        +--> rebuild_alerts en PostgreSQL
        `--> enrich_alerts con Ollama
```

Un fallo de Qdrant u Ollama se registra, pero no revierte el evento clinico o la
prestacion que ya se guardo en PostgreSQL.

## Evolucion del RAG en 0.7.0

La recuperacion ya no selecciona directamente los primeros resultados vectoriales. FastAPI analiza la pregunta mediante reglas explicitas, obtiene un conjunto amplio de candidatos y aplica un reranking local:

```text
Pregunta
  -> categoria, especie, ambito y urgencia
  -> embedding local
  -> candidatos Qdrant
  -> deduplicacion
  -> reranking denso + lexico + metadatos
  -> umbral
  -> prompt con fuentes F0/F1/F2
  -> Ollama
```

Los filtros de seguridad se mantienen como condiciones obligatorias de Qdrant. El reranking no puede ampliar el acceso del usuario.

Los resultados de evaluacion se almacenan en `rag_evaluation_runs`. La nueva pantalla de calidad consulta la coleccion, los documentos registrados y la ultima evaluacion.

## Agregacion de paneles en 0.8.0

El endpoint `/api/v1/dashboard` delega el calculo en
`app.services.dashboard.build_dashboard`. El servicio carga el alcance permitido
con relaciones precargadas, actualiza estados temporales y produce un unico
modelo de respuesta para pantalla y exportacion.

```text
Usuario autenticado
        |
        v
Filtro obligatorio por rol y propietario
        |
        v
Pet + planes + cuotas + servicios + avisos + eventos
        |
        v
Agregador de dashboard
        +--> indicadores y desgloses
        +--> tendencias mensuales
        +--> agenda de proximas acciones
        +--> resumen por mascota para owner
        `--> CSV con el mismo alcance
```

No existe una tabla analitica independiente. Esta decision evita desfases en el
MVP. Prometheus registra el tiempo de generacion y el numero de exportaciones.


## Integracion Wakyma simulada en 0.9.0

El conector aplica una arquitectura de adaptador:

```text
JSON o CSV ficticio
        |
        v
parser de transporte
        |
        v
registros normalizados y validados
        |
        v
upsert por external_id en PostgreSQL
        |
        +--> auditoria de lote y fila
        `--> reindexacion Qdrant + recalculo de avisos
```

La validacion previa recorre el mismo parser y las mismas reglas, pero no modifica entidades de negocio. Los errores se aislan por registro. El contrato normalizado permite sustituir el fichero por un cliente de API real sin cambiar los dominios internos.

## Seguridad y auditoria en 0.10.0

La autenticacion separa el acceso de corta duracion de la sesion renovable:

```text
Inicio de sesion
      |
      +--> access JWT (30 min, sessionStorage)
      `--> refresh JWT (cookie HttpOnly)
                    |
                    `--> SHA-256 en refresh_sessions

Caducidad del access token
      |
      v
POST /auth/refresh
      |
      +--> revoca refresh presentado
      +--> crea nueva sesion rotada
      `--> devuelve nuevo access token
```

`token_version` permite invalidar todos los tokens de un usuario al cambiar la contrasena. Los propietarios creados por la clinica o por la integracion Wakyma quedan restringidos a los endpoints de autenticacion hasta sustituir la credencial temporal.

La auditoria se escribe dentro de la misma transaccion que el cambio funcional cuando es posible:

```text
Router / servicio de negocio
      |
      +--> modifica PostgreSQL
      +--> genera instantanea filtrada
      +--> inserta audit_logs
      `--> commit unico
```

El middleware anade `X-Request-ID`, registra latencia y crea entradas para accesos denegados o escrituras fallidas sin leer el cuerpo HTTP. La pantalla de auditoria solo esta disponible para `clinic` y `staff`; la exportacion queda reservada a `clinic`.


## Evaluacion formal en 0.11.0

El servicio `SystemEvaluator` agrega criterios de aceptacion, pytest y
cobertura, casos controlados del motor preventivo, controles de seguridad, la
evaluacion de recuperacion de VetIA y un benchmark corto. Los resultados se
persisten en `system_evaluation_runs` y se exponen mediante `/api/v1/quality`.

Los datasets se mantienen fuera del codigo en `data/evaluation/`, lo que permite
versionarlos y ampliar los casos sin modificar la logica del evaluador.

## Puerta de dominio y corpus externo (0.14.0)

Antes del embedding, `rag_intelligence.py` analiza vocabulario veterinario,
intencion clinica, alcance de la consulta y senales de otros dominios. Las
consultas marcadas como `out_of_scope` terminan sin invocar Ollama ni Qdrant.

El corpus se divide en:

1. Resumenes Markdown versionados en `data/rag`.
2. Documentos oficiales descargados en `data/rag_external`.
3. Fichas y eventos clinicos ficticios generados desde PostgreSQL.

`app.rag.ingest` extrae texto de Markdown, TXT, PDF y HTML, genera fragmentos con
solapamiento, solicita embeddings a Ollama y reconstruye la coleccion en Qdrant.


## Endurecimiento de cierre (0.15.0)

La capa HTTP incorpora manejadores centralizados que conservan el formato
funcional `detail` y anaden un codigo estable y el identificador de correlacion.
El middleware de contexto mantiene `X-Request-ID`, metricas y auditoria de
rechazos. Los errores internos se registran en el backend, pero no se exponen.

En el frontend, `RoleRoute` deriva a una pantalla de acceso denegado y
`AppErrorBoundary` evita una pantalla en blanco ante errores de renderizado.
El empaquetado separa React, Material UI, Axios y el codigo de aplicacion.

Las pruebas de cierre se dividen en smoke test, matriz de permisos, suite pytest,
evaluacion formal, resiliencia y backup verificable.

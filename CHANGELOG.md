# Changelog

## 0.16.0-rc1

- Candidato de entrega con congelacion expresa de nuevas funciones de negocio y AWS fuera de alcance.
- Nuevo `scripts/reset-demo.ps1` para reconstruir PostgreSQL, Qdrant, avisos y evaluaciones sin eliminar los modelos de Ollama.
- Nuevo `scripts/generate-evidence.ps1` para crear paquetes fechados con pruebas, cobertura, dependencias, evaluaciones, monitorizacion, permisos, backup opcional y hashes SHA-256.
- Nuevo `app.scripts.release_snapshot` con un resumen agregado de datos, evaluaciones y dependencias, sin contactos ni texto clinico.
- Etiqueta visible de entorno `DEMO` y estado `Candidato de entrega` en login y cabecera.
- Documentacion final: instalacion, arquitectura, modelo de datos, endpoints, guion de demo, troubleshooting y lista de entrega.
- Nuevo `scripts/upgrade-v0.16-rc1.ps1` con opciones para reiniciar la demo y generar evidencias.
- Nuevo ADR-015 sobre congelacion del alcance y candidato de entrega.
- Sin cambios de esquema; se mantiene `0009_system_evaluation`.
- 76 pruebas backend superadas, cobertura global del 60 % y build frontend correcto.

## 0.15.0

- Cierre funcional y endurecimiento del MVP sin ampliar el alcance de negocio.
- Respuestas de error de FastAPI compatibles y trazables con `error_code`, `request_id` y cabecera `X-Request-ID`.
- Los errores 500 ya no devuelven detalles internos; los 503 incluyen `Retry-After`.
- Los errores de validacion no reproducen contrasenas, tokens ni valores enviados.
- Nueva pantalla de acceso denegado en React en lugar de redireccion silenciosa.
- Nuevo limite de errores de interfaz para evitar pantallas en blanco y ocultar trazas al usuario.
- Los mensajes funcionales pueden mostrar el identificador de solicitud para facilitar soporte y auditoria.
- Separacion del bundle frontend en bloques React, Material UI y Axios; eliminado el aviso de chunk superior a 500 kB.
- Nuevo `scripts/test-permissions.ps1` con 22 comprobaciones de acceso entre `clinic`, `staff`, `owner` y `technical`.
- Nuevo `scripts/resilience-test.ps1` para detener y recuperar Qdrant y Ollama de forma controlada.
- Nuevo `scripts/release-validation.ps1` para smoke test, permisos, pytest, validacion formal, resiliencia y backup opcional.
- Nuevo `scripts/upgrade-v0.15.ps1` con opciones `-RunPermissionMatrix` e `-IncludeResilience`.
- CI ampliado con validacion sintactica de todos los scripts PowerShell en Windows.
- Matriz de permisos, procedimiento de resiliencia y documentacion de cierre incorporados.
- Sin cambios de esquema ni nueva migracion Alembic.
- 74 pruebas de backend superadas; cobertura global del 60 %.
- Build de React, TypeScript y Vite completado sin advertencia de tamano de chunk.

## 0.14.0

- Filtro determinista de dominio antes de generar embeddings o consultar Qdrant.
- Nuevas decisiones explicables: `accepted`, `out_of_scope`, `low_score` y `no_evidence`.
- Corregidos los falsos positivos G12, capital de Australia, y C07, reparacion de placas base.
- Comparacion de terminos por palabras completas para evitar coincidencias accidentales como `ue` dentro de `que`.
- Dataset de calidad `rag_cases_v2.json` con 23 casos y mas consultas negativas.
- Catalogo versionado de siete fuentes oficiales externas en `data/rag_sources/sources.json`.
- Descargador de fuentes con HTTPS, limite de tamano, SHA-256, fecha, tipo MIME y metadatos sidecar.
- Nuevo script `scripts/download-rag-sources.ps1`, con opciones `-Force` y `-Reindex`.
- Ingesta ampliada a Markdown, TXT, PDF y HTML mediante `pypdf` y `BeautifulSoup`.
- Calidad de VetIA muestra cobertura del corpus externo, errores de descarga y motivo de los casos fallidos.
- Nuevas variables `RAG_EXTERNAL_DOCUMENTS_PATH`, `RAG_SOURCE_MANIFEST` y `RAG_SOURCE_MAX_BYTES`.
- Nuevo script de actualizacion `scripts/upgrade-v0.14.ps1` con reindexacion de Qdrant y descarga externa opcional.
- Sin cambios de esquema ni nueva migracion Alembic.
- ADR-013 sobre filtro de dominio y gobierno de fuentes.
- 71 pruebas de backend superadas; cobertura global del 59 %.
- Build de React, TypeScript y Vite completado correctamente.

## 0.13.0

- Nuevo perfil `technical` para separar administracion tecnica y operacion clinica.
- Menu tecnico exclusivo: Calidad de VetIA, Validacion del MVP, Integracion Wakyma, Auditoria, Seguridad y Estado tecnico.
- Los perfiles `clinic`, `staff` y `owner` dejan de ver y de poder invocar endpoints tecnicos.
- El perfil tecnico no puede acceder a dashboard, clientes, mascotas, planes, avisos ni chat VetIA.
- Integracion Wakyma trasladada por completo al perfil tecnico.
- Usuario local `technical@gamucare.local` en instalaciones nuevas y script idempotente para instalaciones existentes.
- Version visible actualizada a 0.13.0.
- Sin cambios de esquema ni nueva migracion Alembic.
- ADR-012 sobre aislamiento del perfil tecnico.
- Suite de permisos ampliada; **64 pruebas de backend superadas** y cobertura global del 59 %.

## 0.12.0

- Nueva pantalla **Estado tecnico** con disponibilidad y latencia de PostgreSQL, Qdrant y Ollama.
- Nuevos endpoints `/health/dependencies` y `/api/v1/observability/status`.
- Metricas Prometheus para VetIA, Ollama, tokens, Qdrant y dependencias.
- PostgreSQL Exporter, Blackbox Exporter y Alertmanager dentro del perfil `monitoring`.
- Dashboard Grafana ampliado con disponibilidad, errores, latencias, tokens, auditoria y alertas activas.
- Reglas tecnicas por servicios caidos, errores 5xx, latencia, Ollama y Qdrant.
- Logs JSON rotados en fichero y rotacion de los logs del driver Docker.
- Scripts de inicio y parada de monitorizacion, smoke test, backup, verificacion y restauracion.
- Backups con `pg_dump`, snapshot Qdrant, `data.zip` y manifiesto SHA-256.
- Pipeline CI con cobertura minima, artefactos, Compose validation, Buildx y publicacion de imagenes por etiqueta.
- Script `upgrade-v0.12.ps1` compatible con Windows PowerShell 5.1 y con codigos de evaluacion controlados.
- Sin cambios de esquema; se mantiene `0009_system_evaluation` como migracion de cabecera.
- Dos pruebas nuevas; **56 pruebas de backend superadas**.

## 0.11.0

- Version visible debajo del logotipo tanto en el menu lateral como en la pantalla de acceso.
- El asistente pasa a llamarse **VetIA** en toda la interfaz; el termino RAG se conserva solo en codigo y documentacion tecnica.
- Nueva pantalla **Validacion del MVP** para clinica y personal.
- Suite formal con 16 criterios de aceptacion sobre usuarios, pacientes, planes, prevencion, VetIA, seguridad, auditoria e integracion Wakyma.
- Dataset controlado de ocho casos para medir exactitud, precision, recall y matriz de confusion del motor de avisos preventivos.
- Evaluacion integrada de seguridad: politica de contrasenas, bloqueo, duracion de tokens, secreto JWT y redaccion de datos sensibles.
- Reutilizacion de la evaluacion versionada de recuperacion de VetIA y benchmark corto de latencia de la API.
- Ejecucion de pytest con JUnit y cobertura de codigo mediante `pytest-cov`.
- Informe Markdown y JSON persistido en PostgreSQL y en `data/reports` cuando se ejecuta por linea de comandos.
- Nueva tabla `system_evaluation_runs` y migracion Alembic `0009_system_evaluation`.
- Nuevos endpoints `/api/v1/quality/*` para estado, ejecucion, consulta y descarga de informes.
- Nuevas metricas Prometheus para ejecuciones y duracion de la evaluacion formal.
- Pipeline CI actualizado con cobertura, JUnit y artefactos descargables.
- Nuevo script `scripts/upgrade-v0.11.ps1`, compatible con Windows PowerShell 5.1 y con tratamiento robusto de la salida de Docker Compose.
- Corregida la generacion de secretos en `setup-gpu.ps1` y `setup-cpu.ps1` para evitar `RandomNumberGenerator.Fill()` en PowerShell 5.1.
- Seis pruebas nuevas; **54 pruebas de backend superadas** en total.
- Cobertura global medida del backend: **59%**.

## 0.10.0

- Nueva politica de contrasenas: minimo configurable de 12 caracteres, mayuscula, minuscula, numero y caracter especial.
- Cambio obligatorio de la contrasena temporal para propietarios creados manualmente o importados desde Wakyma.
- Bloqueo temporal de cuenta despues de cinco intentos fallidos, con duracion configurable.
- Tokens de acceso de corta duracion y sesiones renovables mediante cookie HttpOnly.
- Rotacion del token de renovacion y almacenamiento exclusivo de su hash en PostgreSQL.
- Revocacion de sesiones al cambiar la contrasena y gestion de sesiones activas desde la interfaz.
- Nueva tabla `audit_logs` con actor, accion, entidad, resultado, fecha, `request_id`, IP y agente de usuario.
- Auditoria de autenticacion, clientes, mascotas, eventos clinicos, planes, pagos, renovaciones, alertas e importaciones.
- Enmascarado de contrasenas, tokens, datos de contacto y texto clinico en auditoria y logs.
- Nueva pantalla **Auditoria** para clinica y personal, con filtros, estadisticas y detalle de cambios.
- Exportacion CSV de auditoria reservada al perfil `clinic` y limitada a 5.000 registros.
- Nueva pantalla **Seguridad** para cambiar la contrasena y revocar sesiones.
- Revision de permisos: `clinic` mantiene escritura, `staff` lectura global y `owner` acceso limitado a sus mascotas.
- Cabeceras de seguridad en Nginx: CSP, proteccion frente a `iframe`, `nosniff`, politica de referencia y permisos del navegador.
- Validacion de configuracion segura cuando `APP_ENV=production`.
- Generacion automatica de un `JWT_SECRET` local aleatorio en los scripts de instalacion y actualizacion.
- Migracion Alembic `0008_security_audit`.
- Nuevo script `scripts/upgrade-v0.10.ps1`, con migracion antes de arrancar la API, espera de `/health/live`, comprobacion de `/health/ready` y diagnostico de logs.
- Corregidas las comprobaciones de arranque de `upgrade-v0.7.ps1`, `upgrade-v0.8.ps1` y `upgrade-v0.9.ps1` para utilizar `/health/live`.
- ADR-009 sobre sesiones seguras y auditoria con minimizacion de datos.
- Siete pruebas nuevas; 48 pruebas de backend superadas en total.

## 0.9.0

- Nueva pantalla **Integracion Wakyma** para clinica y personal.
- Validacion previa de ficheros sin modificar datos.
- Importacion real reservada al perfil `clinic`.
- Soporte de JSON y CSV UTF-8 con propietarios, mascotas y eventos clinicos.
- Actualizacion idempotente por `external_id` para evitar duplicados.
- Validaciones de campos, formatos, duplicados, correos y relaciones entre entidades.
- Procesamiento parcial: los errores se registran por fila sin cancelar registros independientes validos.
- Historial de lotes con checksum SHA-256, usuario, modo, version de esquema y totales.
- Nueva tabla `import_batch_items` para auditoria por registro.
- Generacion y descarga puntual de credenciales temporales para propietarios nuevos.
- Reindexacion de mascotas y recalculo de avisos en segundo plano tras importar.
- Plantillas y datos ficticios de ejemplo en JSON y CSV.
- Nuevas metricas Prometheus para importaciones, duracion y registros procesados.
- Migracion Alembic `0007_wakyma_integration`.
- Script de actualizacion `scripts/upgrade-v0.9.ps1`.
- ADR-008 sobre la frontera del adaptador y la normalizacion del origen.
- Cinco pruebas nuevas; 41 pruebas de backend superadas en total.

## 0.8.0

- Panel de control redisenado y adaptado a los perfiles `clinic`, `staff` y `owner`.
- Indicadores operativos de mascotas, planes, prestaciones, vencimientos y avisos preventivos.
- Resumen economico con importe comprometido, cobrado, pendiente, vencido y proxima cuota.
- Graficos mensuales de servicios realizados y cobros registrados, sin dependencias JavaScript adicionales.
- Desgloses por estado de plan, estado de prestacion, severidad de aviso y especie.
- Rankings de avisos preventivos y tipos de actividad clinica recurrentes.
- Agenda unificada de cuotas, servicios, vencimientos de plan y avisos prioritarios con acceso directo a la ficha.
- Panel especifico del propietario con una tarjeta por mascota, cumplimiento del plan, pagos, servicios y avisos.
- Filtros por periodo, especie y plan aplicados en backend, respetando el alcance del usuario autenticado.
- Exportacion CSV con los indicadores, series temporales y proximas acciones del mismo alcance filtrado.
- Nuevas metricas Prometheus para tiempo de generacion del dashboard y numero de exportaciones.
- Nuevo servicio de agregacion `app.services.dashboard`, separado del router HTTP.
- Sin cambios de esquema ni migracion Alembic en esta version.
- Script de actualizacion `scripts/upgrade-v0.8.ps1`.
- ADR-007 sobre paneles calculados en tiempo real y control de acceso por perfil.
- Cinco pruebas nuevas; 36 pruebas de backend superadas en total.

## 0.7.0

- Base documental ampliada con 8 nuevos resumenes versionados de fuentes oficiales sobre vacunacion, viajes, parasitos, enfermedades vectoriales, nutricion, pacientes senior y seguimiento renal.
- Metadatos de gobierno documental: idioma, audiencia, tipo de fuente, nivel de confianza, etiquetas y fecha de revision.
- Fragmentado Markdown por encabezados con solapamiento controlado.
- Analisis determinista de preguntas por categoria, especie, ambito geografico y posibles terminos de urgencia.
- Recuperacion amplia y reranking explicable mediante similitud densa, coincidencia lexica y metadatos.
- Eliminacion de fragmentos duplicados y nueva calibracion de umbral.
- Respuestas con identificadores de fuente `F0`, `F1`, `F2`, etc.
- Uso de hasta seis mensajes anteriores como contexto conversacional.
- Diagnosticos de recuperacion visibles: confianza, candidatos, resultados, top score y filtros aplicados.
- Nuevo panel `Calidad RAG` para clinic y staff.
- Dataset versionado de 20 casos documentales y clinicos ficticios.
- Metricas de hit rate, MRR, rechazo, cobertura de fuente, paciente, evento y latencia.
- Ejecucion opcional con generacion para comprobar presencia de citas y decision de groundedness.
- Nuevos endpoints `/rag/status`, `/rag/evaluation/latest` y `/rag/evaluation/run`.
- Migracion Alembic `0006_rag_quality` y nueva tabla `rag_evaluation_runs`.
- Script de actualizacion `scripts/upgrade-v0.7.ps1`.
- ADR-006 sobre recuperacion y evaluacion.
- Seis pruebas nuevas; 31 pruebas de backend superadas en total.

## 0.6.0

- Nuevo modulo visual de avisos preventivos para los perfiles `clinic` y `staff`.
- Catalogo versionado de 13 reglas preventivas con categoria, descripcion, fuente, URL, fecha de revision y politica de resolucion automatica.
- Nuevos detectores de recurrencia clinica, variaciones de peso y prestaciones preventivas vencidas.
- Ciclo de vida completo de los avisos: nueva, revisada, resuelta y descartada.
- Registro historico de cada cambio de estado, notas de revision, usuario y fecha.
- Reapertura automatica de avisos resueltos cuando la condicion vuelve a aparecer.
- Resolucion automatica de avisos cuando deja de cumplirse una regla configurada como autorresoluble.
- Prevencion de duplicados mediante una alerta unica por mascota y regla.
- Evidencia estructurada con eventos coincidentes, tendencia de peso y servicios vencidos.
- Explicaciones RAG limitadas a avisos activos y regeneradas cuando cambia la evidencia.
- Reindexacion individual de la mascota en Qdrant tras modificar su ficha, registrar un evento o completar una prestacion.
- Alta de eventos clinicos desde la ficha de la mascota.
- Filtros por estado, severidad, especie, categoria y nombre de mascota, junto con estadisticas del modulo.
- Nuevas metricas Prometheus para reconstrucciones y transiciones de avisos.
- Migracion Alembic `0005_preventive_alerts`.
- Script de actualizacion `scripts/upgrade-v0.6.ps1`.
- Nuevos documentos RAG sobre seguimiento senior, nutricion, BOAS y antecedentes renales.
- Siete pruebas nuevas; 25 pruebas de backend superadas en total.

## 0.5.0

- Asignacion de planes desde la ficha de una mascota.
- Generacion automatica de prestaciones y fechas previstas al crear una suscripcion.
- Cambio inmediato de plan, conservando las prestaciones ya realizadas y cancelando las pendientes.
- Cancelacion con fecha, motivo y trazabilidad historica.
- Renovacion directa por la clinica y programacion del siguiente plan.
- Solicitud de renovacion desde el portal del propietario durante los ultimos 90 dias.
- Bandeja de solicitudes pendientes con aprobacion o rechazo por la clinica.
- Vista de planes que vencen en los proximos 45 dias, incluyendo deuda pendiente.
- Calendario detallado de cuotas con vencimiento, importe, estado y correccion individual.
- Estados de suscripcion `active`, `expiring`, `scheduled`, `expired` y `cancelled`.
- Migracion Alembic `0004_plan_lifecycle` y script `upgrade-v0.5.ps1`.
- Cinco pruebas nuevas para ciclo de vida, prestaciones, cancelacion y cuotas.

## 0.4.0

- Nuevo alcance `pet` en el asistente para consultar una mascota autorizada.
- Seleccion de mascota desde el chat y acceso directo desde su ficha.
- Validacion de propiedad en FastAPI y exclusion de eventos internos para propietarios.
- Contexto combinado de PostgreSQL y recuperacion vectorial filtrada en Qdrant.
- Seguimiento de pago completo o financiado entre 2 y 12 cuotas.
- Calculo de importe total, pagado, pendiente y valor de cada cuota.
- Edicion del pago reservada al perfil `clinic`.
- Migracion Alembic `0003_plan_payments` y script `upgrade-v0.4.ps1`.
- Datos ficticios con estados de pago variados.

## 0.3.0

- Indexacion en Qdrant de fichas de mascotas y eventos clinicos ficticios.
- Dos alcances de chat: documentacion general e historiales clinicos.
- Acceso al RAG clinico limitado a `clinic` y `staff` desde FastAPI.
- Fuentes clinicas enlazadas con la ficha de cada mascota.
- Nuevos historiales recurrentes para demostrar patrones articulares,
  respiratorios, dermatologicos, auriculares, digestivos y renales.
- Embeddings por lotes para reducir el tiempo de reindexacion.
- Explicaciones de avisos preventivos basadas en RAG y Ollama.
- Script `upgrade-v0.3.ps1` para actualizar sin borrar volumenes.
- Nuevos parametros `RAG_CLINICAL_TOP_K` y `RAG_ALERT_TOP_K`.

## 0.2.1

- Corregidas las URLs `resolved` de `frontend/package-lock.json` para utilizar
  el registro publico de npm.

## 0.2.0

- Reduccion a tres perfiles: clinica, personal y propietario.
- Separacion real de permisos de lectura y escritura en la API.
- Creacion automatica de una cuenta por propietario.
- Gestion de alta, edicion, baja logica y reactivacion de clientes y mascotas.

## 0.1.1

- Correccion de la configuracion TypeScript para la compilacion del frontend.

## 0.1.0

- Primera version funcional del MVP.

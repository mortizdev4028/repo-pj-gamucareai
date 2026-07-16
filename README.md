# ¡¡IMPORTANTE!!

En la carpeta docs, se encuentran los documentos de memoria y justificación del proyecto.

# GamuCare AI

Aplicacion web para controlar planes de salud veterinarios, prestaciones,
pagos, renovaciones, alertas preventivas y consultas mediante VetIA, el asistente documental basado en RAG.

Los propietarios, mascotas e historiales incluidos son ficticios. Los planes
LifeCare se han cargado a partir de la documentacion facilitada por la clinica.

## Version actual: 0.16.0-rc1

Candidato de entrega con el alcance funcional congelado y AWS excluido:

- Dataset de demostracion reconstruible sin borrar los modelos de Ollama.
- Paquete automatico de evidencias con pruebas, cobertura, calidad, validacion y hashes.
- Resumen agregado de la instalacion sin datos de contacto ni textos clinicos.
- Documentacion final de instalacion, arquitectura, modelo de datos, endpoints, demostracion y resolucion de problemas.
- Etiqueta visible `DEMO · Candidato de entrega` en la interfaz.
- Lista de comprobacion previa a v1.0.0.
- Sin cambios de esquema ni nueva migracion Alembic.

## Perfiles

| Perfil | Permisos |
|---|---|
| Clinica | Gestion completa de clientes, mascotas, planes, pagos, renovaciones y avisos. |
| Personal | Consulta global y analisis clinico en modo solo lectura. |
| Propietario | Consulta de sus mascotas, pagos, servicios y solicitud de renovacion. |
| Tecnico | Calidad de VetIA, validacion, integracion Wakyma, auditoria, seguridad y estado tecnico. |

## Componentes

- React, TypeScript y Material UI: interfaz "responsive".
- FastAPI, SQLAlchemy y Alembic: API y logica de negocio.
- PostgreSQL: clientes, mascotas, historiales, planes y pagos.
- Qdrant: documentos, fichas clinicas y eventos vectorizados.
- Ollama: modelo generativo y embeddings locales.
- Nginx: publicacion web y proxy inverso.
- Prometheus y Grafana: monitorizacion opcional.

## Requisitos

- Windows 10 u 11.
- Docker Desktop con WSL2.
- Controlador NVIDIA actualizado para utilizar la GPU.
- Aproximadamente 12 GB libres.

## Primera instalacion con GPU

Abre PowerShell dentro de la carpeta del proyecto:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-gpu.ps1
```

El primer arranque descarga `llama3.2:3b` y `nomic-embed-text`.

Accesos:

- Aplicacion: http://localhost:8080
- Swagger: http://localhost:8000/docs
- Qdrant: http://localhost:6333/dashboard

## Actualizacion desde 0.15.x

Copia esta version sobre la carpeta anterior, conserva el fichero `.env` y no
elimines los volumenes. Despues ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\upgrade-v0.16-rc1.ps1
```

El script conserva los volumenes y los datos existentes. Para reconstruir el dataset
ficticio de la demostracion se utiliza un comando separado y destructivo:

```powershell
.\scripts\reset-demo.ps1
```

Para crear el paquete de evidencias de una ejecucion real:

```powershell
.\scripts\generate-evidence.ps1 -IncludeMonitoring -IncludePermissions
```

Para una instalacion limpia:

```powershell
.\scripts\reset.ps1
.\scripts\setup-gpu.ps1
```

`reset.ps1` elimina las bases de datos, los vectores y los modelos descargados.

## Alternativa sin GPU

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-cpu.ps1
```


## Documentacion de entrega

- `docs/INSTALLATION.md`: instalacion desde cero.
- `docs/FINAL_ARCHITECTURE.md`: arquitectura y flujo de VetIA.
- `docs/DATA_MODEL.md`: entidades y relaciones.
- `docs/ENDPOINTS.md`: inventario de API y errores.
- `docs/DEMO_GUIDE.md`: guion de defensa.
- `docs/TROUBLESHOOTING.md`: resolucion de problemas.
- `docs/DELIVERY_CHECKLIST.md`: control previo a v1.0.0.


## Monitorizacion local

La instalacion y la actualizacion arrancan el perfil `monitoring` salvo que se
use `-SkipMonitoring`. Tambien puede gestionarse de forma independiente:

```powershell
.\scripts\start-monitoring.ps1
.\scripts\stop-monitoring.ps1
```

Accesos:

- Estado tecnico: http://localhost:8080/system-status
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093

Grafana utiliza las credenciales definidas en `.env`. Prometheus consulta la
API, Qdrant, PostgreSQL y sondas HTTP de los servicios principales.


## Validacion de cierre

Comprobacion normal, sin detener servicios:

```powershell
.\scripts\release-validation.ps1 -IncludeMonitoring
```

Matriz de permisos con los usuarios de demostracion:

```powershell
.\scripts\test-permissions.ps1
```

Prueba controlada de caida y recuperacion de Qdrant y Ollama:

```powershell
.\scripts\resilience-test.ps1
```

La prueba de resiliencia no elimina volumenes. Detiene cada servicio, espera que la API
lo marque como `down`, lo arranca de nuevo y confirma su recuperacion.

## Backup y restauracion

Crear una copia:

```powershell
.\scripts\backup.ps1
```

Verificarla:

```powershell
.\scripts\verify-backup.ps1 -BackupPath .\backups\gamucare-AAAAMMDD-HHMMSS
```

Restaurar PostgreSQL y Qdrant:

```powershell
.\scripts\restore.ps1 -BackupPath .\backups\gamucare-AAAAMMDD-HHMMSS -Force
```

Para recuperar tambien documentos, datasets e informes, anade `-RestoreData`.
Los modelos de Ollama no se copian porque pueden volver a descargarse.

## Smoke test

```powershell
.\scripts\smoke-test.ps1 -IncludeMonitoring
```

## Usuarios de demostracion

Todos utilizan la contrasena `GamuCare123!`.

| Perfil | Usuario |
|---|---|
| Clinica | clinic@gamucare.local |
| Personal de solo lectura | staff@gamucare.local |
| Tecnico | technical@gamucare.local |
| Propietario | owner01@example.test |

El perfil tecnico solo accede a calidad de VetIA, validacion, integracion, auditoria, seguridad y estado tecnico.

Existen propietarios desde `owner01@example.test` hasta
`owner15@example.test`.


## Paneles de control

La pagina inicial cambia segun el perfil autenticado. Clinica y personal disponen de indicadores globales, resumen economico, tendencias, recurrencias y una agenda de actuaciones. El perfil `staff` visualiza los mismos datos, pero todas las operaciones de modificacion continúan bloqueadas por FastAPI.

Los propietarios solo reciben agregados de sus propias mascotas. Cada tarjeta muestra el plan, porcentaje de cumplimiento, servicios pendientes o vencidos, avisos activos, saldo pendiente y siguiente cuota.

Los filtros de periodo, especie y plan se procesan en el backend. La exportacion CSV utiliza exactamente los mismos filtros y permisos que la pantalla.

## Gestion de planes

Desde la ficha de una mascota, el perfil de clinica puede:

1. Asignar uno de los planes compatibles con la especie.
2. Elegir fecha de inicio y modalidad de pago.
3. Cambiar el plan activo de forma inmediata.
4. Cancelarlo indicando fecha y motivo.
5. Renovarlo y dejar el siguiente periodo programado.
6. Actualizar las cuotas abonadas.

Al crear una suscripcion, el backend genera las prestaciones a partir del
catalogo del plan. Los servicios periodicos siguen su frecuencia configurada y
los servicios con varios usos se distribuyen durante la vigencia. Las consultas
ilimitadas, descuentos y beneficios se muestran como disponibles durante todo
el periodo.

La cancelacion no borra informacion: conserva las prestaciones realizadas y
marca como canceladas las que estaban pendientes.

## Gestion de cuotas

Cada suscripcion conserva un calendario de cobros. En la ficha se muestra para
cada cuota:

- Numero de cuota.
- Fecha de vencimiento.
- Importe.
- Estado pendiente, vencida, pagada o cancelada.
- Fecha en la que se registro el pago.

La clinica puede marcar una cuota como pagada o corregir un pago registrado por
error. El importe pagado y el saldo pendiente se recalculan a partir del numero
de cuotas abonadas. Si cambia la modalidad o el numero de cuotas, se genera un
nuevo calendario para la suscripcion.

## Renovacion desde el portal del propietario

Durante los ultimos 90 dias del plan, el propietario puede pulsar **Solicitar
renovacion**. La peticion aparece en la pantalla **Planes LifeCare** para que la
clinica la apruebe o la rechace.

Al aprobarla se crea una nueva suscripcion que comienza el dia siguiente a la
finalizacion del plan actual. Si se solicita antes de vencer, se muestra como
**Programada** y no sustituye al plan en curso.

## Planes proximos a vencer

La pantalla **Planes LifeCare** incluye una lista de suscripciones que finalizan
en los proximos 45 dias. Para cada una se muestra:

- Mascota y propietario.
- Plan actual y fecha de vencimiento.
- Dias restantes.
- Estado del pago e importe pendiente.
- Acceso directo a la ficha.

## Consultar una mascota como propietario

1. Accede con `owner01@example.test`.
2. Abre **Asistente** y selecciona **Datos de la mascota**.
3. Elige una de tus mascotas.
4. Prueba preguntas como:

```text
Que servicios tiene pendientes?
Cuanto queda por pagar del plan?
Cuando fue la ultima vacuna?
Ha tenido problemas de oidos anteriormente?
Que avisos preventivos tiene activos?
```

FastAPI valida que la mascota pertenezca al usuario. Las notas internas no
visibles quedan fuera del prompt y de la busqueda vectorial.

## Probar VetIA con historiales clinicos

Accede como clinica o personal, abre **Asistente** y selecciona **Historiales
clinicos**. Algunas consultas de ejemplo:

```text
Que problemas recurrentes aparecen en perros braquicefalicos?
Hay varios pacientes con molestias articulares?
Que casos de otitis se repiten y en que mascotas?
Que gatos muestran problemas renales o perdida de peso?
```

## Avisos preventivos con RAG

Los avisos se generan en dos capas separadas:

1. El motor de reglas evalua datos estructurados, recurrencias del historial, tendencias de peso y prestaciones vencidas.
2. Qdrant recupera documentos e historiales relacionados y Ollama redacta una explicacion. El LLM no crea el aviso ni realiza un diagnostico.

Desde **Avisos preventivos**, clinica y personal pueden filtrar por estado, severidad, especie, categoria o mascota. Solo la clinica puede revisar, resolver, descartar o reabrir avisos.

Cada regla muestra su fuente y cada cambio de estado queda registrado. Los avisos resueltos pueden reabrirse automaticamente si vuelve a cumplirse la condicion. Los descartados solo se reabren de forma manual.

Para reconstruirlos manualmente:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api python -m app.scripts.sync_risk_rules
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api python -m app.scripts.enrich_alerts
```

La ficha de una mascota permite registrar eventos clinicos. Al guardar un evento, la aplicacion actualiza los vectores de esa mascota y recalcula sus avisos en segundo plano.

## Descargar e indexar fuentes oficiales externas

El ZIP no redistribuye documentos completos de terceros. Incluye un catalogo
versionado en `data/rag_sources/sources.json` y un descargador que obtiene cada
fichero desde el organismo oficial, guarda su SHA-256 y crea los metadatos de
ingesta.

```powershell
.\scripts\download-rag-sources.ps1 -Reindex
```

Para repetir todas las descargas:

```powershell
.\scripts\download-rag-sources.ps1 -Force -Reindex
```

Las fuentes descargadas quedan en `data/rag_external`. Antes de utilizarlas fuera
del MVP academico deben revisarse sus condiciones de uso y vigencia.

## Evaluar la recuperacion de VetIA

Accede como `technical` y abre **Calidad de VetIA**. La pantalla muestra el estado de Qdrant, el numero de vectores, la cobertura documental, el estado de las fuentes externas y la ultima evaluacion.

El modo de recuperacion usa el dataset versionado y es el mas rapido. El modo con generacion tambien solicita respuestas a Ollama y comprueba la presencia de citas. El filtro de dominio rechaza consultas ajenas a veterinaria antes de crear el embedding.

Desde PowerShell tambien puede ejecutarse:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api python -m app.scripts.evaluate_rag
```

Para incluir generacion:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api python -m app.scripts.evaluate_rag --with-generation
```

Las metricas automaticas no sustituyen la revision humana de fidelidad y utilidad clinica.


## Validacion formal del MVP

Accede como `technical` y abre **Validacion del MVP**. La pantalla combina:

- 16 criterios de aceptacion de datos y funciones.
- Pruebas automatizadas con cobertura.
- Ocho casos controlados del motor de avisos preventivos.
- Controles de seguridad.
- Evaluacion de recuperacion de VetIA.
- Benchmark corto de la API.

Solo el perfil `technical` puede iniciar una nueva ejecucion. El resultado queda almacenado
en PostgreSQL y puede descargarse como informe Markdown. Desde PowerShell:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api python -m app.scripts.evaluate_system
```

Para omitir temporalmente VetIA:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api python -m app.scripts.evaluate_system --skip-vetia
```

Los datasets estan en `data/evaluation/` y los informes generados por linea de
comandos en `data/reports/`.

## Integracion simulada con Wakyma

Accede como `technical` y abre **Integracion Wakyma**.

1. Descarga una plantilla JSON o CSV.
2. Selecciona el fichero.
3. Ejecuta **Validar** para comprobarlo sin modificar datos.
4. Revisa los errores por fila.
5. El perfil `technical` puede ejecutar **Importar**.

La segunda importacion del mismo fichero actualiza por `external_id` y no duplica registros. Los propietarios nuevos reciben una contrasena temporal que solo se devuelve al finalizar la operacion; conviene descargarla en ese momento.

Los ejemplos se encuentran en:

```text
data/seed/wakyma_import_v2.json
data/seed/wakyma_import_v2.csv
```

Tras una importacion real, las mascotas afectadas se reindexan y recalculan sus avisos en segundo plano. La aplicacion deja claro que se trata de un conector ficticio y no de una API real de Wakyma.


## Seguridad y auditoria

La opcion **Seguridad** permite cambiar la contrasena, revisar las sesiones creadas y revocar las que ya no se reconozcan. Las cuentas nuevas de propietarios deben sustituir la contrasena temporal antes de acceder a mascotas, planes o asistente.

La opcion **Auditoria** esta disponible exclusivamente para el perfil tecnico. Registra autenticacion, cambios en clientes y mascotas, eventos clinicos, planes, pagos, avisos e importaciones. Los valores sensibles y el texto clinico libre se enmascaran antes de persistir la entrada. El perfil tecnico puede exportar el resultado a CSV.

Configuracion local por defecto:

```text
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
MAX_FAILED_LOGIN_ATTEMPTS=5
LOGIN_LOCK_MINUTES=15
PASSWORD_MIN_LENGTH=12
```

En un despliegue HTTPS debe establecerse `APP_ENV=production` y `REFRESH_COOKIE_SECURE=true`. Consulta [Seguridad y auditoria](docs/SECURITY.md) para la matriz completa de permisos.

## Comandos habituales

Arrancar con GPU:

```powershell
.\scripts\start-gpu.ps1
```

Detener:

```powershell
.\scripts\stop.ps1
```

Ver logs:

```powershell
docker compose logs -f api web ollama
```

Activar monitorizacion:

```powershell
docker compose --profile monitoring up -d prometheus grafana
```

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Usuario: `admin`
- Contrasena: `gamucare`

## Pruebas

El backend incluye 76 pruebas sobre salud de la API, errores trazables, roles, seguridad, pagos, acceso a VetIA, suscripciones, integracion, motor preventivo y metadatos de release. La cobertura global medida en la v0.16.0-rc1 es del **60%**.

Dentro del contenedor de la API:

```powershell
docker compose exec api pytest -q
```

## Documentacion

- [Instalacion final](docs/INSTALLATION.md)
- [Arquitectura final](docs/FINAL_ARCHITECTURE.md)
- [Modelo de datos](docs/DATA_MODEL.md)
- [Inventario de endpoints](docs/ENDPOINTS.md)
- [Guion de demostracion](docs/DEMO_GUIDE.md)
- [Resolucion de problemas](docs/TROUBLESHOOTING.md)
- [Lista de entrega](docs/DELIVERY_CHECKLIST.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Guia funcional](docs/USER_GUIDE.md)
- [Decisiones tecnicas](docs/DECISIONS.md)
- [Fuentes del RAG](docs/SOURCES.md)
- [Seguridad y auditoria](docs/SECURITY.md)
- [Cambios por version](CHANGELOG.md)
- [Historial consolidado](docs/RELEASE_HISTORY.md)
- [Estrategia de evaluacion](docs/QUALITY_EVALUATION.md)
- [Matriz de permisos](docs/PERMISSION_MATRIX.md)
- [Pruebas de resiliencia](docs/RESILIENCE_TESTS.md)
- [Operacion local](docs/OPERATIONS.md)
- [Detalle de la version 0.16.0-rc1](docs/releases/v0.16.0-rc1.md)
- [ADR del motor preventivo](docs/architecture/decisions/ADR-005-preventive-alert-engine.md)
- [ADR de recuperacion y evaluacion RAG](docs/architecture/decisions/ADR-006-rag-retrieval-and-evaluation.md)
- [ADR de evaluacion formal](docs/architecture/decisions/ADR-010-formal-mvp-evaluation.md)

- [ADR del adaptador Wakyma](docs/architecture/decisions/ADR-008-wakyma-adapter-boundary.md)
- [ADR de sesiones y auditoria](docs/architecture/decisions/ADR-009-session-security-and-audit.md)

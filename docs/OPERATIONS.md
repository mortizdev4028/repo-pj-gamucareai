# Operacion local

## Servicios

El entorno base contiene PostgreSQL, Qdrant, Ollama, FastAPI y Nginx. El perfil
`monitoring` anade PostgreSQL Exporter, Blackbox Exporter, Prometheus,
Alertmanager y Grafana.

## Health checks

- `/health/live`: proceso FastAPI activo.
- `/health/ready`: acceso a PostgreSQL.
- `/health/dependencies`: PostgreSQL, Qdrant y Ollama con latencia.
- `/metrics/`: metricas Prometheus.

`/health/dependencies` devuelve HTTP 503 cuando una dependencia esta caida. La
interfaz autenticada usa `/api/v1/observability/status` para mostrar el mismo
diagnostico sin exponer credenciales.

## Metricas principales

- `gamucare_http_requests_total` y `gamucare_http_request_duration_seconds`.
- `gamucare_vetia_requests_total` y `gamucare_vetia_request_duration_seconds`.
- `gamucare_ollama_requests_total`, latencia y tokens.
- `gamucare_qdrant_searches_total` y latencia.
- Metricas de alertas, auditoria, dashboards, calidad e importaciones.
- `pg_*` desde PostgreSQL Exporter y `probe_*` desde Blackbox Exporter.

## Logs

FastAPI escribe JSON en stdout y en `/var/log/gamucare/api.jsonl`. El fichero
rota por tamano y numero de copias. Docker tambien limita cada log JSON a tres
ficheros de 10 MB. No se registran contrasenas, tokens ni cuerpos clinicos.

## Alertas tecnicas

Prometheus evalua reglas de disponibilidad, errores 5xx, latencia, fallos de
Ollama y fallos de Qdrant. Alertmanager las agrupa y las muestra localmente. No
se configura envio de correo porque la aplicacion se mantiene en entorno local.

## Comandos

```powershell
.\scripts\start-monitoring.ps1
.\scripts\stop-monitoring.ps1
.\scripts\smoke-test.ps1 -IncludeMonitoring
```

## Actualizar y ampliar el corpus RAG

Descargar las fuentes oficiales catalogadas y reindexar:

```powershell
.\scripts\download-rag-sources.ps1 -Reindex
```

Repetir las descargas aunque el fichero ya exista:

```powershell
.\scripts\download-rag-sources.ps1 -Force -Reindex
```

La operacion crea `data/rag_external/download-report.json`. Un error en una
fuente no elimina las descargas correctas, pero el script termina con codigo no
cero para que el operador revise el informe.

Reindexar sin descargar:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec -T api python -m app.rag.ingest
```

La reindexacion reconstruye la coleccion de Qdrant. No modifica propietarios,
mascotas, planes ni historiales en PostgreSQL.


## Validacion de cierre incorporada en 0.15.0

La validacion normal se ejecuta sin provocar indisponibilidad:

```powershell
.\scripts\release-validation.ps1 -IncludeMonitoring
```

La variante ampliada anade caida controlada de Qdrant/Ollama y genera un backup
que se verifica al terminar:

```powershell
.\scripts\release-validation.ps1 -IncludeMonitoring -IncludeResilience -IncludeBackup
```

La prueba de resiliencia debe ejecutarse en local o durante una ventana de
mantenimiento, porque detiene servicios reales durante unos segundos.

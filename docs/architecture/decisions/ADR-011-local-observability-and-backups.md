# ADR-011: Observabilidad y backups del despliegue local

## Estado

Aceptada en v0.12.0.

## Contexto

El TFM exige monitorizacion, logging, trazabilidad y automatizacion. El alcance
final se limita a Docker Compose sobre Windows y WSL2. La solucion debe ser
demostrable sin depender de servicios externos.

## Decision

- Prometheus recoge metricas de FastAPI, Qdrant y PostgreSQL.
- Blackbox Exporter comprueba endpoints HTTP.
- Alertmanager agrupa alertas tecnicas localmente.
- Grafana se provisiona con datasource y dashboard versionados.
- FastAPI mantiene logs JSON rotados en un volumen y Docker limita stdout.
- PostgreSQL se copia con `pg_dump` y Qdrant mediante snapshots.
- Cada backup incluye un manifiesto SHA-256 verificable.

## Alternativas descartadas

- cAdvisor: anade dependencias y montajes del host con comportamiento desigual
  en Docker Desktop para Windows.
- Copiar directamente los volumenes: no garantiza una copia consistente con
  servicios en ejecucion.
- Incluir modelos de Ollama: aumenta varios gigabytes y son reproducibles.

## Consecuencias

La operacion es repetible y visible durante la defensa. El envio externo de
alertas y la alta disponibilidad quedan fuera del alcance del MVP.

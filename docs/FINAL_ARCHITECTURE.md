# Arquitectura final de GamuCare AI

## Alcance congelado

GamuCare AI es un MVP local desplegado mediante Docker Compose. AWS queda fuera
del alcance final. Todos los datos personales y clinicos son ficticios.

```text
Navegador
   |
   v
Nginx + React/TypeScript :8080
   |
   v
FastAPI :8000
   |--------------------|--------------------|
   v                    v                    v
PostgreSQL :5432     Qdrant :6333       Ollama :11434
negocio, usuarios,    embeddings,        gamucare-llm y
pagos, auditoria      corpus e historiales nomic-embed-text
   |
   +--> logs JSON y metricas /metrics
                |
                v
Prometheus --> Grafana
     |
     +--> Alertmanager
     +--> Blackbox Exporter
     +--> PostgreSQL Exporter
     +--> cAdvisor
```

## Flujo de VetIA

```text
Pregunta
  -> control de permisos
  -> filtro de dominio
  -> embedding
  -> busqueda Qdrant
  -> filtros por perfil/mascota
  -> reranking
  -> umbral y decision explicable
  -> contexto con citas
  -> Ollama
  -> respuesta y auditoria tecnica
```

Decisiones de recuperacion:

- `accepted`: evidencia suficiente.
- `out_of_scope`: consulta ajena al dominio veterinario.
- `low_score`: candidatos por debajo del nivel exigido.
- `no_evidence`: no existe evidencia util.

## Perfiles

- `clinic`: operacion clinica y comercial.
- `staff`: lectura de informacion funcional.
- `owner`: acceso exclusivo a sus mascotas.
- `technical`: calidad, validacion, integracion, auditoria, seguridad y estado tecnico.

La ocultacion del menu no es el control principal. FastAPI vuelve a verificar el
rol y la pertenencia del recurso en cada endpoint.

## Persistencia

- `postgres_data`: datos estructurados.
- `qdrant_data`: vectores.
- `ollama_data`: modelos descargados.
- `prometheus_data`, `grafana_data`, `alertmanager_data`: observabilidad.
- `app_logs`: log JSON rotado de FastAPI.
- `./data`: corpus, datasets, informes y fuentes descargadas.

## Disponibilidad y seguridad

- Health checks `live`, `ready` y `dependencies`.
- JWT de corta duracion y refresh cookie rotada.
- Bloqueo de cuenta y politica de contrasenas.
- Auditoria transversal con `request_id`.
- Errores 500 genericos y validaciones sin eco de valores sensibles.
- Backups verificables de PostgreSQL, Qdrant y datos del proyecto.

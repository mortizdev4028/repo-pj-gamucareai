# Modelo de datos resumido

## Identidad y seguridad

- `users`: cuenta, rol, estado, bloqueo y version de token.
- `refresh_sessions`: sesiones renovables y revocables.
- `audit_logs`: acciones, actor, resultado, cambios y `request_id`.

## Operacion veterinaria

- `owners` 1--N `pets`.
- `pets` 1--N `clinical_events`.
- La baja de propietarios y mascotas es logica desde la API.
- Los historiales ficticios se indexan en Qdrant sin datos de contacto del propietario.

## Planes LifeCare

- `health_plans` 1--N `plan_services`.
- `pets` 1--N `pet_plan_subscriptions`.
- `pet_plan_subscriptions` 1--N `subscription_services`.
- `pet_plan_subscriptions` 1--N `plan_installments`.
- `renewal_requests` registra las solicitudes del propietario y su resolucion.

## Prevencion

- `risk_rules`: catalogo versionado de reglas.
- `risk_alerts`: resultado de evaluar cada paciente.
- `alert_status_history`: trazabilidad de revision, resolucion, descarte y reapertura.

## IA y calidad

- `rag_documents`: gobierno de fuentes, hash y estado de ingesta.
- `rag_evaluation_runs`: ejecuciones de Calidad de VetIA.
- `system_evaluation_runs`: Validacion del MVP.
- `chat_sessions` y `chat_messages`: conversaciones, fuentes y latencia.

## Integracion

- `import_batches`: lote Wakyma simulado.
- `import_batch_items`: resultado individual de cada fila o entidad.

La migracion de cabecera del candidato sigue siendo `0009_system_evaluation`; la
v0.16.0-rc1 no altera el esquema.

# ADR-015 — Candidato de entrega y congelacion del alcance

## Estado

Aceptado en v0.16.0-rc1.

## Contexto

El MVP ya cubre operacion veterinaria ficticia, planes, pagos, prevencion,
integracion simulada, VetIA, seguridad, auditoria y observabilidad. Continuar
anadiendo funciones aumentaria el riesgo de regresion y dificultaria la defensa.
AWS se ha eliminado expresamente del alcance final.

## Decision

- Congelar nuevas funciones de negocio.
- Crear un dataset demo reconstruible sin eliminar modelos de Ollama.
- Generar evidencias tecnicas en una carpeta fechada y verificable por SHA-256.
- Consolidar documentacion de instalacion, arquitectura, datos, endpoints,
  demostracion, problemas y entrega.
- Mostrar de forma visible que la aplicacion es un entorno demo y un candidato.
- Admitir desde este punto solo correcciones de defectos antes de v1.0.0.

## Consecuencias

La entrega es mas reproducible y defendible. Los scripts destructivos requieren
confirmacion y el paquete de evidencias depende de una ejecucion real en Docker
Desktop. El candidato no implica aptitud para produccion ni validacion clinica.

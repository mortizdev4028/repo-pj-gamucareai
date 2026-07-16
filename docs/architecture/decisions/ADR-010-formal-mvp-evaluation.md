# ADR-010: Evaluacion formal versionada dentro del producto

## Estado

Aceptada para v0.11.0.

## Contexto

El TFM necesita evidencias repetibles, no solo una demostracion visual. Ya
existia una evaluacion de recuperacion del RAG, pero no una vision conjunta de
funciones, reglas preventivas, seguridad, pruebas y rendimiento.

## Decision

Crear una suite formal que utilice datasets JSON versionados, pytest, cobertura,
la evaluacion de VetIA y un benchmark acotado. Cada ejecucion se almacena en
PostgreSQL y genera un informe Markdown.

## Alternativas descartadas

- Mantener resultados manuales en una hoja de calculo: poca repetibilidad.
- Ejecutar todo exclusivamente en CI: dificulta mostrar resultados con datos
  locales durante la demo.
- Incorporar una plataforma de testing externa: complejidad excesiva para un
  MVP individual.

## Consecuencias

- Los resultados pueden compararse entre versiones.
- La memoria puede incluir metricas y evidencias trazables.
- La evaluacion completa consume recursos y puede tardar por Ollama.
- La revision clinica humana continua siendo obligatoria.

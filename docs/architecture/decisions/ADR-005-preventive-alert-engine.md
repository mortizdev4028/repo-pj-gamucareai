# ADR-005: Motor determinista para avisos preventivos y LLM solo explicativo

- **Estado:** Aceptada
- **Fecha:** 2026-07-15
- **Version:** 0.6.0

## Contexto

La aplicacion debe localizar situaciones que merezcan revision, como recurrencias clinicas, cambios de peso o prestaciones vencidas. Permitir que un LLM genere directamente estos avisos haria dificil explicar por que se activaron, evitar duplicados y comprobar su comportamiento.

## Decision

Los avisos se originan mediante reglas deterministas y versionadas. Cada regla registra condiciones, severidad, fuente y politica de resolucion. El RAG y Ollama se utilizan despues para redactar una explicacion basada en la evidencia y en documentos recuperados.

## Consecuencias positivas

- Cada aviso puede auditarse.
- El mismo conjunto de datos produce el mismo resultado.
- Es posible probar las condiciones sin ejecutar un modelo generativo.
- El veterinario puede revisar, resolver o descartar el aviso.
- El LLM no actua como sistema de diagnostico.

## Consecuencias negativas

- El catalogo necesita mantenimiento manual.
- Las reglas basadas en texto libre pueden perder sinonimos o detectar coincidencias imprecisas.
- Los umbrales operativos deben revisarse con profesionales veterinarios antes de un uso real.

## Alternativas descartadas

### Deteccion completa mediante LLM

Se descarta por falta de reproducibilidad y trazabilidad.

### Modelo predictivo entrenado con historiales

No se dispone de un conjunto de datos real, representativo y autorizado. No seria justificable entrenar un modelo clinico con los datos ficticios del MVP.

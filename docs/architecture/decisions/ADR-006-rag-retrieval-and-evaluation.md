# ADR-006: Recuperacion hibrida explicable y evaluacion versionada del RAG

- **Estado:** Aceptada
- **Fecha:** 2026-07-15
- **Version:** 0.7.0

## Contexto

La primera implementacion recuperaba directamente los fragmentos con mayor similitud densa. El sistema funcionaba, pero era dificil saber por que una fuente habia sido elegida, comparar versiones o detectar regresiones al cambiar documentos, umbrales o modelos.

El equipo disponible tiene una GTX 1060 de 6 GB. Incorporar un reranker neuronal adicional aumentaria el consumo, la descarga de modelos y la complejidad de despliegue.

## Decision

Se mantiene `nomic-embed-text` para embeddings y se incorpora un reranking determinista que combina similitud densa, coincidencia lexica y metadatos controlados.

Se añade un dataset versionado de preguntas y una evaluacion propia con metricas de recuperacion, rechazo y latencia. Los resultados se almacenan en PostgreSQL y se muestran en la aplicacion.

## Alternativas consideradas

### Mantener solo similitud vectorial

Ventaja: menor codigo.

Inconveniente: menor control de ambito, fuentes y regresiones.

### Incorporar un cross-encoder

Ventaja: potencial mejora de relevancia.

Inconveniente: mayor consumo de memoria y tiempo, modelo adicional y peor adecuacion al equipo objetivo.

### Utilizar RAGAS u otro servicio externo

Ventaja: metricas y componentes ya implementados.

Inconveniente: dependencias adicionales, coste o necesidad de API externa, menor control sobre datos clinicos ficticios y mas dificultad para explicar el flujo completo.

## Consecuencias

Positivas:

- La recuperacion es auditable.
- Es posible comparar versiones.
- Las metricas se ejecutan localmente.
- No se añade un modelo pesado.
- Las fuentes oficiales reciben una bonificacion limitada y visible.

Negativas:

- La formula necesita calibracion empirica.
- Un reranking basado en reglas no entiende todos los matices semanticos.
- La evaluacion automatica debe complementarse con revision humana.

## Criterio de revision futura

Se reconsiderara un cross-encoder cuando el despliegue disponga de mas capacidad de GPU. Cualquier sustitucion debera compararse con el dataset versionado y superar las metricas de la linea base sin empeorar significativamente la latencia.

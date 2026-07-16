# ADR-013: filtro de dominio y gobierno de fuentes externas

## Estado
Aceptado en la version 0.14.0.

## Contexto
Qdrant siempre devuelve los vectores mas proximos aunque la consulta no tenga
relacion con veterinaria. En la evaluacion aparecieron falsos positivos para
preguntas sobre la capital de Australia y la reparacion de placas base. Subir el
umbral global podia perjudicar preguntas veterinarias validas.

El corpus local tambien necesitaba admitir documentos oficiales mas extensos sin
redistribuir dentro del repositorio copias completas de terceros ni perder la
trazabilidad de la version descargada.

## Decision
1. Aplicar un filtro determinista de dominio antes de crear el embedding.
2. Usar evidencia positiva veterinaria, intencion clinica, vocabulario operativo
   de la mascota y señales explicitas de dominios ajenos.
3. Registrar una decision explicable: `accepted`, `out_of_scope`, `low_score` o
   `no_evidence`.
4. Mantener un manifiesto versionado de fuentes oficiales.
5. Descargar los documentos desde el organismo de origen y guardar URL, fecha,
   tamano y SHA-256 en un fichero sidecar.
6. Admitir Markdown, texto, PDF y HTML en el proceso de ingesta.
7. No permitir que el LLM decida el dominio ni los permisos de acceso.

## Consecuencias
- Las consultas fuera de alcance no consumen embeddings ni busquedas en Qdrant.
- Los rechazos pueden explicarse y medirse en el dataset de calidad.
- El umbral vectorial sigue dedicado a la relevancia documental.
- Los documentos externos requieren conectividad y pueden cambiar o desaparecer.
- La extraccion de PDF depende de que el documento contenga texto; los PDF
  escaneados sin capa textual se omiten y deben prepararse manualmente.
- Las condiciones de uso y vigencia de cada fuente deben revisarse antes de un
  uso distinto del MVP academico.

# Estrategia de evaluacion del MVP

## Capas evaluadas

1. **Criterios de aceptacion**: integridad minima de usuarios, pacientes, planes,
   pagos, reglas, documentos, auditoria e importaciones.
2. **Pruebas automatizadas**: pytest, JUnit y cobertura del backend.
3. **Avisos preventivos**: exactitud, precision, recall y matriz de confusion
   sobre casos controlados.
4. **Seguridad**: contrasenas, bloqueo, tokens, secreto JWT y redaccion.
5. **VetIA**: tasa de acierto de recuperacion, MRR, rechazo y latencia.
6. **Rendimiento**: muestra acotada de solicitudes al endpoint de vida.

## Umbral global

La suite asigna una puntuacion sobre 100:

| Area | Peso |
|---|---:|
| Criterios de aceptacion | 30 |
| Pruebas automatizadas | 25 |
| Avisos preventivos | 20 |
| Seguridad | 10 |
| Recuperacion de VetIA | 10 |
| Rendimiento API | 5 |

El resultado se considera apto a partir de 80 puntos, siempre que no fallen las
pruebas automatizadas ni los controles de seguridad.

## Interpretacion

Las metricas miden el comportamiento del software y casos previamente
etiquetados. No demuestran validez diagnostica ni reemplazan la revision
veterinaria humana.

## Cambios de evaluacion en 0.14.0

El dataset activo es `rag_cases_v2.json`. Incluye consultas negativas sobre
informatica, cultura general y deporte. Antes de crear el embedding, VetIA
clasifica el dominio de forma determinista.

Las decisiones de recuperacion son:

- `accepted`: hay evidencia por encima del umbral.
- `out_of_scope`: la consulta no pertenece al dominio veterinario.
- `low_score`: existen candidatos, pero ninguno supera el umbral.
- `no_evidence`: Qdrant no devuelve candidatos utilizables.

El `top_score` continua siendo una medida de similitud del mejor fragmento
aceptado, no una probabilidad de respuesta correcta. En un rechazo por dominio
el valor es cero porque Qdrant no llega a consultarse.

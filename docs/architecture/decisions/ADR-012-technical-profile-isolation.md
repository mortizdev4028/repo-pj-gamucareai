# ADR-012: aislamiento del perfil tecnico

## Estado
Aceptado en la version 0.13.0.

## Contexto
Las funciones de calidad, validacion, integracion, auditoria, seguridad y observabilidad estaban visibles para perfiles clinicos. Esto mezclaba operacion asistencial con administracion de plataforma.

## Decision
Se introduce el rol `technical`. Es el unico perfil con acceso a Calidad de VetIA, Validacion del MVP, Integracion Wakyma, Auditoria, Seguridad y Estado tecnico. Los perfiles `clinic`, `staff` y `owner` conservan exclusivamente las funciones de negocio que les corresponden.

La separacion se aplica en React y en FastAPI. Ocultar el menu no se considera una medida de seguridad suficiente.

## Consecuencias
- Menor exposicion de datos y herramientas tecnicas al personal no responsable de la plataforma.
- Matriz de permisos mas clara para la memoria y la defensa.
- La cuenta tecnica no puede consultar fichas, planes, pagos ni conversaciones mediante la API.
- La integracion simulada Wakyma pasa a ser responsabilidad operativa del perfil tecnico.

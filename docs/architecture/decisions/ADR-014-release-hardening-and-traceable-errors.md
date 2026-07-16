# ADR-014: cierre funcional, errores trazables y pruebas operativas

## Estado
Aceptado en la version 0.15.0.

## Contexto
El MVP ya contenia los modulos funcionales previstos. Antes de congelar el
alcance era necesario mejorar el comportamiento ante errores, demostrar la
separacion de permisos con pruebas repetibles y validar la deteccion de caidas
sin incorporar nuevos modulos de negocio.

FastAPI devolvia mensajes correctos, pero no todos incluian un identificador que
permitiera relacionar la incidencia con auditoria y logs. React redirigia de
forma silenciosa cuando un perfil intentaba abrir una ruta no permitida y un
error de renderizado podia dejar una pantalla en blanco.

## Decision
1. Mantener el campo `detail` para no romper el frontend existente.
2. Anadir `error_code` y `request_id` a los errores HTTP.
3. No devolver excepciones internas ni valores rechazados por validacion.
4. Incluir `X-Request-ID` en la respuesta para correlacion con logs y auditoria.
5. Mostrar una pagina de acceso denegado en lugar de una redireccion silenciosa.
6. Incorporar un limite global de errores React con mensaje funcional.
7. Automatizar una matriz representativa de permisos de los cuatro roles.
8. Automatizar la caida y recuperacion controlada de Qdrant y Ollama.
9. Validar la sintaxis de scripts PowerShell en un runner Windows del pipeline.
10. No detener PostgreSQL automaticamente en las pruebas de resiliencia.

## Consecuencias
- Soporte puede localizar una peticion concreta sin exponer trazas al usuario.
- Los mensajes existentes que leen `detail` siguen funcionando.
- Las pruebas operativas son repetibles, pero la matriz depende de credenciales
  de demostracion validas.
- La prueba de resiliencia produce indisponibilidad deliberada y debe ejecutarse
  en local o en una ventana de mantenimiento.
- No hay cambios de esquema ni migracion de datos.

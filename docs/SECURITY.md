# Seguridad y auditoria

## Matriz de permisos

| Funcion | Clinica | Personal | Propietario |
|---|---:|---:|---:|
| Consultar clientes y mascotas | Si | Si | Solo propias |
| Modificar clientes, mascotas e historiales | Si | No | No |
| Gestionar planes, pagos y renovaciones | Si | No | Solicitar renovacion |
| Consultar avisos y RAG clinico global | Si | Si | Solo contexto autorizado |
| Cambiar estado de avisos | Si | No | No |
| Validar importacion Wakyma | Si | Si | No |
| Ejecutar importacion Wakyma | Si | No | No |
| Consultar auditoria | Si | Si | No |
| Exportar auditoria | Si | No | No |
| Gestionar sus propias sesiones | Si | Si | Si |

Los permisos se comprueban en FastAPI. Ocultar un boton en React no se considera un control de seguridad.

## Politica de contrasenas

- Minimo de 12 caracteres.
- Una letra mayuscula.
- Una letra minuscula.
- Un numero.
- Un caracter especial.
- No puede contener la parte local del correo cuando esta tiene cuatro o mas caracteres.

Las cuentas creadas por la clinica o por el importador se marcan para cambio obligatorio. Hasta completar ese cambio solo pueden acceder a los endpoints de autenticacion necesarios.

## Sesiones

- Access token: 30 minutos por defecto.
- Refresh token: 7 dias por defecto.
- Cookie HttpOnly y `SameSite=Lax` en local.
- Rotacion del refresh token en cada uso.
- Revocacion individual desde **Seguridad**.
- Revocacion global al cambiar la contrasena mediante `token_version`.

## Bloqueo de cuenta

Despues de cinco credenciales incorrectas, la cuenta se bloquea durante 15 minutos. Los valores se configuran con `MAX_FAILED_LOGIN_ATTEMPTS` y `LOGIN_LOCK_MINUTES`.

## Datos excluidos de logs y auditoria

- Contrasenas y hashes.
- JWT, cookies y cabeceras de autorizacion.
- Telefonos y direcciones completas.
- Contenido de diagnosticos, tratamientos, observaciones y notas clinicas.
- Cuerpos completos de las peticiones HTTP.

## Variables sensibles

`.env` esta excluido de Git. Nunca se debe subir el valor real de `JWT_SECRET`, credenciales de PostgreSQL ni credenciales de servicios externos.

Para produccion:

```text
APP_ENV=production
REFRESH_COOKIE_SECURE=true
JWT_SECRET=<valor aleatorio de al menos 32 caracteres>
```

El despliegue productivo debe terminar TLS antes de Nginx o utilizar un balanceador HTTPS.

## Respuesta ante una sesion comprometida

1. Abrir **Seguridad** y revocar la sesion desconocida.
2. Cambiar la contrasena si existe duda sobre las credenciales.
3. Revisar **Auditoria** por usuario, IP, resultado y periodo.
4. Exportar el intervalo desde una cuenta `clinic` cuando sea necesario conservar evidencia.


## Errores trazables y acceso denegado en 0.15.0

Las respuestas de error mantienen `detail` para compatibilidad y anaden
`error_code` y `request_id`. La misma correlacion se devuelve en la cabecera
`X-Request-ID` y puede buscarse en logs y auditoria.

Los errores de validacion no reproducen los valores recibidos y los errores 500
usan un mensaje generico. React muestra una pagina explicita al intentar abrir
una ruta no permitida, pero la autorizacion real sigue residiendo en FastAPI.

La matriz completa y su prueba automatizada se documentan en
`docs/PERMISSION_MATRIX.md`.

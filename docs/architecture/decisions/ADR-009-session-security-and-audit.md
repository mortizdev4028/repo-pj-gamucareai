# ADR-009: Sesiones renovables y auditoria con minimizacion de datos

- Estado: aceptada
- Fecha: 2026-07-16

## Contexto

La aplicacion manejara informacion personal, clinica y economica ficticia durante el MVP. El token JWT inicial era de larga duracion y no existia un mecanismo central para revocar sesiones ni reconstruir quien habia modificado un registro. Tambien era necesario evitar que la propia auditoria se convirtiera en una segunda copia de los historiales clinicos.

## Decision

Se adopta un esquema de dos tokens:

- Token de acceso JWT de corta duracion, enviado en la cabecera `Authorization`.
- Token de renovacion JWT en cookie HttpOnly, rotado en cada uso y almacenado en PostgreSQL solo mediante SHA-256.

Cada usuario dispone de `token_version`. Cambiar la contrasena incrementa esa version y revoca las sesiones previas.

Se crea un registro de auditoria append-only desde la aplicacion. Cada entrada contiene actor, accion, entidad, resultado, fecha, identificador de peticion y metadatos tecnicos. Las instantaneas se filtran antes de persistirlas:

- Secretos, contrasenas, tokens y cookies: eliminados.
- Datos de contacto: enmascarados o sustituidos.
- Diagnosticos, tratamientos, descripciones y notas: no duplicados.

## Alternativas valoradas

### Mantener un unico JWT largo

Descartada porque dificulta revocar una sesion comprometida y obliga a elegir entre seguridad y comodidad.

### Guardar refresh tokens completos

Descartada porque una lectura de la base de datos permitiria reutilizarlos. El hash basta para comprobar la sesion presentada.

### Registrar cuerpos HTTP completos

Descartada porque podria almacenar contrasenas, datos personales y texto clinico sin necesidad operativa.

### Utilizar exclusivamente logs de texto

Descartada porque no ofrecen consultas fiables por entidad, actor o periodo y pueden rotar antes de una revision.

## Consecuencias positivas

- Sesiones revocables y de menor exposicion.
- Cambio de contrasena invalida accesos anteriores.
- Trazabilidad de cambios funcionales y accesos denegados.
- Menor riesgo de filtrar datos sensibles en logs o auditoria.
- Informacion util para la memoria, pruebas y operacion del MVP.

## Consecuencias negativas

- PostgreSQL almacena y limpia mas registros auxiliares.
- La rotacion de sesiones anade una llamada HTTP cuando caduca el access token.
- El modo HTTP local no puede utilizar una cookie `Secure`.
- El registro append-only depende aun de los permisos de la misma aplicacion.

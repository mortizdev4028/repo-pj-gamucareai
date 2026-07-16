# ADR-007: Paneles por perfil calculados en tiempo real

- Estado: aceptada
- Fecha: 2026-07-15

## Contexto

GamuCare ya almacenaba planes, cuotas, prestaciones, historiales y avisos, pero la pantalla inicial solo mostraba siete contadores. Era necesario ofrecer informacion distinta a la clinica y a los propietarios sin duplicar datos ni debilitar el control de acceso.

## Decision

Los paneles se calculan en FastAPI a partir de las tablas operativas y siempre despues de aplicar el alcance del usuario autenticado. Se utiliza un unico contrato enriquecido con secciones especificas para propietario. La exportacion CSV reutiliza el mismo servicio de agregacion.

La interfaz representa tendencias con componentes propios basados en Material UI y CSS, evitando una dependencia adicional para el MVP.

## Alternativas consideradas

### Tablas de resumen actualizadas por trabajos programados

Mejoran el rendimiento a gran escala, pero introducen sincronizacion, estados obsoletos y mas infraestructura.

### Calculo completo en React

Se descarta porque obligaria a descargar demasiados datos y permitiria errores de alcance o manipulacion de agregados.

### Paneles y endpoints completamente separados por rol

Ofrece contratos mas pequenos, pero duplica consultas, tipos y mantenimiento. El contrato comun facilita pruebas y evolucion.

## Consecuencias

- Los indicadores reflejan siempre el estado real de la base de datos.
- Los permisos no dependen de ocultar componentes en React.
- El coste de calculo crece con el volumen; en despliegues de mayor escala se valorara cache o vistas materializadas.
- El mismo servicio alimenta pantalla y CSV, reduciendo discrepancias.

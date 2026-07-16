# Matriz de permisos final

La autorizacion se aplica en dos niveles: el frontend oculta o bloquea rutas y
FastAPI vuelve a validar el rol en cada endpoint. Ocultar el menu nunca se
considera una medida de seguridad suficiente.

| Area | clinic | staff | owner | technical |
|---|---:|---:|---:|---:|
| Dashboard operativo | Lectura | Lectura | Solo datos propios | No |
| Clientes | CRUD | Lectura | No | No |
| Mascotas | CRUD | Lectura | Solo propias | No |
| Historial clinico | CRUD | Lectura | Solo eventos visibles propios | No |
| Planes, cuotas y servicios | CRUD | Lectura | Solo propios y solicitud de renovacion | No |
| Avisos preventivos | Gestion | Lectura | Resumen propio mediante mascota | No |
| VetIA documental/clinica | Si | Si | Solo mascota propia y fuentes publicas | No |
| Calidad de VetIA | No | No | No | Si |
| Validacion del MVP | No | No | No | Si |
| Integracion Wakyma | No | No | No | Si |
| Auditoria | No | No | No | Si |
| Seguridad tecnica | No | No | No | Si |
| Estado tecnico | No | No | No | Si |

## Prueba automatizada

```powershell
.\scripts\test-permissions.ps1
```

El script inicia sesion con los cuatro usuarios de demostracion y ejecuta 22
comprobaciones representativas. Valida tanto accesos permitidos como respuestas
`403` esperadas.

La prueba utiliza por defecto `GamuCare123!`. Si las contrasenas de demostracion
se han cambiado:

```powershell
.\scripts\test-permissions.ps1 -Password "NuevaClaveLocal"
```

El script no modifica datos. Los endpoints permitidos elegidos son de lectura.

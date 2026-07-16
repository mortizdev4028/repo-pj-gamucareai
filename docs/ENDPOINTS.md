# Inventario de endpoints

Todos los endpoints funcionales utilizan el prefijo `/api/v1`. La documentacion
OpenAPI completa se publica en `http://localhost:8000/docs`.

| Area | Prefijo | Operaciones principales | Perfiles |
|---|---|---|---|
| Autenticacion | `/auth` | login, refresh, logout, cambio de clave, sesiones, perfil | autenticado |
| Dashboard | `/dashboard` | indicadores y CSV | clinic, staff, owner |
| Propietarios | `/owners` | listado, alta, cambio, baja y activacion | clinic; lectura staff |
| Mascotas | `/pets` | listado, ficha, alta, cambio, eventos y baja | segun rol y propiedad |
| Planes | `/plans` | catalogo, suscripciones, cuotas, renovaciones y servicios | clinic; lectura limitada |
| Avisos | `/alerts` | listado, reglas, estados, reconstruccion y enriquecimiento | clinic/staff |
| VetIA | `/chat/ask` | consulta documentada o clinica | clinic, staff, owner |
| Wakyma | `/integrations/wakyma` | estado, importacion, lotes y plantillas | technical |
| Calidad VetIA | `/rag` | estado y evaluacion | technical |
| Validacion MVP | `/quality` | estado, ejecucion e informe | technical |
| Auditoria | `/audit` | listado, estadisticas y CSV | technical |
| Observabilidad | `/observability/status` | dependencias y latencia | technical |

Endpoints sin prefijo:

- `GET /health/live`
- `GET /health/ready`
- `GET /health/dependencies`
- `GET /metrics`

## Convencion de errores

```json
{
  "detail": "No tienes permisos para esta operacion",
  "error_code": "forbidden",
  "request_id": "identificador-de-la-peticion"
}
```

El mismo identificador se devuelve en la cabecera `X-Request-ID`.

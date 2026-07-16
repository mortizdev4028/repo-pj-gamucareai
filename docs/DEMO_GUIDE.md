# Guion de demostracion

Duracion objetivo: 12--15 minutos.

## Preparacion

```powershell
.\scripts\reset-demo.ps1
.\scripts\generate-evidence.ps1 -IncludeMonitoring -IncludePermissions
```

Abre previamente la aplicacion, Grafana y la carpeta de evidencias.

## 1. Problema y arquitectura — 1 minuto

Explica que GamuCare integra planes preventivos, datos clinicos ficticios y un
asistente local documentado. Muestra el diagrama de `FINAL_ARCHITECTURE.md`.

## 2. Perfil clinica — 3 minutos

1. Entra con `clinic@gamucare.local`.
2. Muestra el dashboard, clientes y mascotas.
3. Abre una mascota con historial recurrente.
4. Enseña plan, cuotas, prestaciones y aviso preventivo.
5. Destaca que todas las acciones quedan auditadas.

## 3. VetIA — 3 minutos

Desde el perfil clinica prueba:

```text
Que casos de otitis se repiten y en que mascotas?
Como se realiza el seguimiento de una enfermedad renal cronica?
Cual es la capital de Australia?
```

La tercera debe rechazarse como `out_of_scope` y no utilizar Qdrant ni Ollama.
Muestra las citas y aclara que VetIA no diagnostica.

## 4. Separacion de perfiles — 2 minutos

- `staff`: mismos datos de consulta, sin escritura.
- `owner01@example.test`: solo sus mascotas y su informacion economica.
- `technical@gamucare.local`: solo pantallas tecnicas.

Muestra la matriz automatizada de permisos como evidencia.

## 5. Calidad y validacion — 2 minutos

- Calidad de VetIA: retrieval, MRR, top score y rechazos.
- Validacion del MVP: criterios funcionales y tecnicos globales.

Diferencia claramente recuperar informacion de generar una respuesta.

## 6. Operacion — 2 minutos

Muestra:

- Estado tecnico.
- Grafana y Prometheus.
- Alertmanager.
- Un backup verificado o su evidencia.

## 7. Cierre — 1 minuto

Limitaciones:

- Datos ficticios.
- Corpus acotado y versionado.
- Sin certificacion clinica.
- Sin AWS en el alcance final.
- MVP local, no plataforma de produccion.

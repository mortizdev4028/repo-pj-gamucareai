# Instalacion local

## Requisitos

- Windows 10/11 con Docker Desktop y WSL2.
- Docker Compose v2.
- 16 GB de RAM como minimo; 32 GB recomendados.
- Aproximadamente 20 GB libres para imagenes, modelos, datos y evidencias.
- GPU NVIDIA opcional. La configuracion GPU esta pensada para una GTX 1060 de 6 GB o superior.

## Instalacion GPU

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-gpu.ps1
```

La primera ejecucion descarga las imagenes Docker y los modelos de Ollama. Los
modelos quedan en el volumen `ollama_data`, por lo que no se descargan de nuevo
al reconstruir API o frontend.

## Instalacion CPU

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-cpu.ps1
```

## Accesos

| Componente | URL |
|---|---|
| Aplicacion | http://localhost:8080 |
| API y OpenAPI | http://localhost:8000/docs |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |
| Qdrant | http://localhost:6333/dashboard |

## Usuarios demo

Todos utilizan `GamuCare123!` en el entorno academico.

| Perfil | Usuario |
|---|---|
| Clinica | `clinic@gamucare.local` |
| Personal | `staff@gamucare.local` |
| Tecnico | `technical@gamucare.local` |
| Propietario | `owner01@example.test` |

## Fuentes documentales externas

El ZIP no redistribuye los documentos completos de terceros. Para descargarlos,
registrar su hash e indexarlos:

```powershell
.\scripts\download-rag-sources.ps1 -Reindex
```

## Verificacion

```powershell
.\scripts\smoke-test.ps1 -IncludeMonitoring
```

La aplicacion debe mostrar `v0.16.0-rc1` y la etiqueta `DEMO · Candidato de entrega`.

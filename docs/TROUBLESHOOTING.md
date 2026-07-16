# Resolucion de problemas

## La API no responde

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml ps
docker compose -f docker-compose.yml -f docker-compose.gpu.yml logs --tail=200 api
```

Comprueba `http://localhost:8000/health/live` y despues `/health/ready`.

## Ollama tarda o responde con error

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml logs --tail=200 ollama
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile setup run --rm ollama-init
```

La primera carga del modelo es mas lenta. En 6 GB de VRAM puede existir descarga
parcial a RAM; no debe interpretarse como fallo mientras el endpoint responda.

## Qdrant no contiene los documentos nuevos

```powershell
.\scripts\download-rag-sources.ps1 -Reindex
```

O solo reconstruye la coleccion existente:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec -T api python -m app.rag.ingest
```

## Calidad de VetIA devuelve casos antiguos

La evaluacion es historica. Ejecuta una nueva evaluacion despues de reindexar y
consulta la ejecucion mas reciente.

## Prometheus no muestra todos los targets

```powershell
.\scripts\start-monitoring.ps1
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile monitoring ps
```

En Prometheus abre `Status -> Targets`. Blackbox necesita que los endpoints sean
accesibles desde la red Docker, no solo desde Windows.

## La matriz de permisos falla en login

El script usa por defecto la clave demo. Si fue cambiada:

```powershell
.\scripts\test-permissions.ps1 -Password "TuClaveLocal"
```

## Restauracion

Verifica siempre el backup antes de restaurar:

```powershell
.\scripts\verify-backup.ps1 -BackupPath .\backups\gamucare-AAAAMMDD-HHMMSS
.\scripts\restore.ps1 -BackupPath .\backups\gamucare-AAAAMMDD-HHMMSS -Force
```

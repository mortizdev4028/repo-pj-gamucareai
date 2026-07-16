# Backup y restauracion

## Contenido

Cada copia contiene:

- `postgres.dump`: formato custom de `pg_dump`.
- `qdrant.snapshot`: snapshot de la coleccion vectorial.
- `data.zip`: documentos RAG, datasets, ejemplos e informes.
- `manifest.json`: version, fecha, nombres logicos, tamanos y SHA-256.

Los modelos de Ollama no se incluyen. Su descarga es reproducible mediante los
scripts de instalacion y evita copias de varios gigabytes.

## Crear

```powershell
.\scripts\backup.ps1
```

`-IncludeLogs` anade el log JSON actual de FastAPI.

## Verificar

```powershell
.\scripts\verify-backup.ps1 -BackupPath <directorio>
```

## Restaurar

```powershell
.\scripts\restore.ps1 -BackupPath <directorio> -Force
```

La restauracion detiene temporalmente API y frontend, reemplaza PostgreSQL y la
coleccion de Qdrant y vuelve a arrancar la aplicacion. `-RestoreData` recupera
tambien el contenido de `data.zip`. Se recomienda crear un backup nuevo antes
de cualquier restauracion.

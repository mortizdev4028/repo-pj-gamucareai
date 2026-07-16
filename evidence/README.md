# Evidencias generadas

Esta carpeta se mantiene vacia en el repositorio. El comando siguiente crea un
subdirectorio fechado con pruebas, cobertura, evaluaciones y estado técnico:

```powershell
.\scripts\generate-evidence.ps1 -IncludeMonitoring -IncludePermissions
```

Los resultados generados no deben versionarse automáticamente porque reflejan
una ejecución concreta y pueden ocupar espacio. Cada paquete incluye
`files.sha256` para comprobar su integridad.

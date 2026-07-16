# Pruebas controladas de resiliencia

## Objetivo

Demostrar que GamuCare detecta la perdida de dependencias y que estas pueden
recuperarse sin eliminar volumenes ni reconstruir la instalacion.

## Ejecucion

```powershell
.\scripts\resilience-test.ps1
```

La secuencia aplicada a Qdrant y Ollama es:

1. Detener el contenedor con `docker compose stop`.
2. Consultar `/health/dependencies` hasta observar `down`.
3. Confirmar que el health agregado devuelve estado degradado.
4. Arrancar el contenedor con `docker compose start`.
5. Esperar hasta que la dependencia vuelva a aparecer como `up`.

Para probar solo una dependencia:

```powershell
.\scripts\resilience-test.ps1 -SkipOllama
.\scripts\resilience-test.ps1 -SkipQdrant
```

## Salvaguardas

- No usa `down`, `rm`, `reset` ni elimina volumenes.
- El bloque `finally` intenta arrancar el servicio aunque falle una comprobacion.
- PostgreSQL no se detiene automaticamente: al ser la base transaccional, su
  prueba debe hacerse en una copia o ventana controlada.
- La prueba verifica deteccion y recuperacion, no valida una restauracion de datos.

## Evidencia esperada

Durante la caida, la pantalla Estado tecnico debe mostrar la dependencia como
no disponible. Prometheus y Blackbox deben reflejar el fallo y, si se mantiene
el tiempo definido en las reglas, Alertmanager debe recibir la alerta.

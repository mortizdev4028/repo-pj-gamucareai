$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env desde .env.example"
}

$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

Write-Host "Reconstruyendo API y frontend..."
docker compose @Compose build api web
docker compose @Compose up -d postgres qdrant ollama api web

Write-Host "Esperando a la API y a la migracion de PostgreSQL..."
$ApiReady = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health/ready" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $ApiReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 3
    }
}
if (-not $ApiReady) {
    throw "La API no ha arrancado. Revisa: docker compose logs api"
}

Write-Host "Creando el detalle de cuotas para las suscripciones existentes..."
docker compose @Compose exec api python -m app.scripts.backfill_installments

Write-Host "Actualizacion 0.5.0 completada. Aplicacion: http://localhost:8080"
Write-Host "No se han eliminado volumenes ni datos existentes."

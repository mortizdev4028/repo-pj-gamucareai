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
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health/live" -UseBasicParsing -TimeoutSec 2
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

Write-Host "Configurando estados de pago ficticios..."
docker compose @Compose exec api python -m app.scripts.configure_demo_payments

Write-Host "Reindexando fichas e historiales para las consultas por mascota..."
docker compose @Compose exec api python -m app.rag.ingest

Write-Host "Actualizacion 0.4.0 completada. Aplicacion: http://localhost:8080"

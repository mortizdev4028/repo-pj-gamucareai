$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env desde .env.example"
}

$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

Write-Host "Reconstruyendo API y frontend para GamuCare AI 0.6.0..."
docker compose @Compose build api web
docker compose @Compose up -d postgres qdrant ollama api web

Write-Host "Esperando a la API y a la migracion 0005_preventive_alerts..."
$ApiReady = $false
for ($i = 0; $i -lt 80; $i++) {
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
    throw "La API no ha arrancado. Revisa: docker compose -f docker-compose.yml -f docker-compose.gpu.yml logs api"
}

Write-Host "Sincronizando el catalogo versionado de reglas preventivas..."
docker compose @Compose exec api python -m app.scripts.sync_risk_rules

Write-Host "Reindexando documentacion e historiales en Qdrant..."
docker compose @Compose exec api python -m app.rag.ingest

Write-Host "Recalculando y enriqueciendo avisos preventivos..."
docker compose @Compose exec api python -m app.scripts.enrich_alerts

Write-Host "Ejecutando pruebas del backend..."
docker compose @Compose exec api pytest -q

Write-Host "Actualizacion 0.6.0 completada. Aplicacion: http://localhost:8080"
Write-Host "No se han eliminado volumenes ni datos existentes."

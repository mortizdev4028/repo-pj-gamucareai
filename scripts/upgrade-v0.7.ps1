$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env desde .env.example"
}

$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

Write-Host "Reconstruyendo API y frontend para GamuCare AI 0.7.0..."
docker compose @Compose build api web
docker compose @Compose up -d postgres qdrant ollama api web

Write-Host "Esperando a la API y a la migracion 0006_rag_quality..."
$ApiReady = $false
for ($i = 0; $i -lt 80; $i++) {
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
    throw "La API no ha arrancado. Revisa: docker compose -f docker-compose.yml -f docker-compose.gpu.yml logs api"
}

Write-Host "Reindexando la base documental ampliada y los historiales..."
docker compose @Compose exec api python -m app.rag.ingest

Write-Host "Ejecutando la evaluacion de recuperacion RAG..."
docker compose @Compose exec api python -m app.scripts.evaluate_rag

Write-Host "Ejecutando pruebas del backend..."
docker compose @Compose exec api pytest -q

Write-Host "Actualizacion 0.7.0 completada. Aplicacion: http://localhost:8080"
Write-Host "Panel de calidad RAG: http://localhost:8080/rag-quality"
Write-Host "No se han eliminado volumenes ni datos existentes."

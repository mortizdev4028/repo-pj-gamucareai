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

Write-Host "Esperando a la API..."
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health/live" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) { break }
    } catch {
        Start-Sleep -Seconds 3
    }
}

Write-Host "Anadiendo historiales ficticios recurrentes..."
docker compose @Compose exec api python -m app.scripts.enrich_demo_histories

Write-Host "Reindexando documentos e historiales en Qdrant..."
docker compose @Compose exec api python -m app.rag.ingest

Write-Host "Generando explicaciones RAG para los avisos preventivos..."
docker compose @Compose exec api python -m app.scripts.enrich_alerts

Write-Host "Actualizacion 0.3.0 completada. Aplicacion: http://localhost:8080"

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env desde .env.example"
}

$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

Write-Host "Reconstruyendo API y frontend para GamuCare AI 0.8.0..."
docker compose @Compose build api web
docker compose @Compose up -d postgres qdrant ollama api web

Write-Host "Esperando a la API..."
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

Write-Host "Comprobando migraciones pendientes..."
docker compose @Compose exec api alembic upgrade head

Write-Host "Ejecutando las pruebas del backend..."
docker compose @Compose exec api pytest -q

Write-Host "Actualizacion 0.8.0 completada. Aplicacion: http://localhost:8080"
Write-Host "La version no modifica el esquema ni elimina datos, vectores o modelos."

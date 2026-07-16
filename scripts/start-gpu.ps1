$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
Write-Host "GamuCare AI disponible en http://localhost:8080"

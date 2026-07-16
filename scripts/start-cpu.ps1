$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
docker compose up -d
Write-Host "GamuCare AI disponible en http://localhost:8080"

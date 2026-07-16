$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$answer = Read-Host "Se eliminaran datos, vectores y modelos. Escribe BORRAR para continuar"
if ($answer -ne "BORRAR") {
    Write-Host "Operacion cancelada"
    exit 0
}
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile monitoring down -v --remove-orphans
Write-Host "Entorno eliminado"

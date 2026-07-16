$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile monitoring down

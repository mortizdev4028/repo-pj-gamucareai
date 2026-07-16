param([switch]$SkipMonitoring)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env desde .env.example"
}


$JwtLine = Get-Content ".env" | Where-Object { $_ -match "^JWT_SECRET=" } | Select-Object -Last 1
$JwtValue = if ($JwtLine) { ($JwtLine -split '=', 2)[1] } else { "" }
if (-not $JwtValue -or $JwtValue -eq "change-this-local-secret-before-production" -or $JwtValue.Length -lt 32) {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    $secret = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    $lines = Get-Content ".env" | Where-Object { $_ -notmatch "^JWT_SECRET=" }
    $lines += "JWT_SECRET=$secret"
    [System.IO.File]::WriteAllLines((Join-Path $Root ".env"), $lines, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "JWT_SECRET local generado en .env"
}

$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

docker compose @Compose up -d postgres qdrant ollama
Write-Host "Esperando a Ollama..."
Start-Sleep -Seconds 10

docker compose @Compose --profile setup run --rm ollama-init
docker compose @Compose up -d --build api web

Write-Host "Esperando a la API..."
for ($i = 0; $i -lt 40; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health/live" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) { break }
    } catch {
        Start-Sleep -Seconds 3
    }
}

docker compose @Compose exec api python -m app.scripts.enrich_demo_histories
docker compose @Compose exec api python -m app.rag.ingest
docker compose @Compose exec api python -m app.scripts.enrich_alerts
docker compose @Compose exec api python -m app.scripts.evaluate_rag
if (-not $SkipMonitoring) {
    & (Join-Path $PSScriptRoot "start-monitoring.ps1")
}
Write-Host "GamuCare AI disponible en http://localhost:8080"

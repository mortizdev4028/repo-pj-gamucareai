$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml", "--profile", "monitoring")

function Invoke-Compose {
    param([string[]]$Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker compose @Compose @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previous }
    if ($code -ne 0) { throw ("docker compose ha fallado con codigo {0}: {1}" -f $code, ($Arguments -join " ")) }
}

Write-Host "Iniciando monitorizacion local..."
Invoke-Compose -Arguments @("up", "-d", "postgres-exporter", "blackbox-exporter", "alertmanager", "prometheus", "grafana")
Write-Host "Grafana:      http://localhost:3000"
Write-Host "Prometheus:   http://localhost:9090"
Write-Host "Alertmanager: http://localhost:9093"

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml", "--profile", "monitoring")

$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & docker compose @Compose stop grafana prometheus alertmanager blackbox-exporter postgres-exporter 2>&1 | ForEach-Object { Write-Host $_ }
    $code = $LASTEXITCODE
}
finally { $ErrorActionPreference = $previous }
if ($code -ne 0) { throw ("No se pudo detener la monitorizacion. Codigo: {0}" -f $code) }

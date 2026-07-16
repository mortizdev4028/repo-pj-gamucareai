param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [switch]$RestoreData,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
if (-not $Force) { throw "La restauracion reemplaza datos. Repite el comando con -Force." }
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")
$resolved = (Resolve-Path $BackupPath).Path

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

function Invoke-Docker {
    param([string[]]$Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previous }
    if ($code -ne 0) { throw ("docker ha fallado con codigo {0}: {1}" -f $code, ($Arguments -join " ")) }
}

& (Join-Path $PSScriptRoot "verify-backup.ps1") -BackupPath $resolved
$manifest = Get-Content (Join-Path $resolved "manifest.json") -Raw | ConvertFrom-Json
$postgresFile = Join-Path $resolved "postgres.dump"
$qdrantFile = Join-Path $resolved "qdrant.snapshot"
if (-not (Test-Path $postgresFile)) { throw "Falta postgres.dump." }
if (-not (Test-Path $qdrantFile)) { throw "Falta qdrant.snapshot." }

Write-Host "Deteniendo API y frontend..."
Invoke-Compose -Arguments @("stop", "web", "api")
Invoke-Compose -Arguments @("up", "-d", "postgres", "qdrant")

Write-Host "Restaurando PostgreSQL..."
$tempDump = "/tmp/gamucare-restore.dump"
Invoke-Docker -Arguments @("cp", $postgresFile, ("gamucare-postgres:{0}" -f $tempDump))
Invoke-Compose -Arguments @("exec", "-T", "postgres", "pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges", "-U", $manifest.postgres_user, "-d", $manifest.postgres_database, $tempDump)
Invoke-Compose -Arguments @("exec", "-T", "postgres", "rm", "-f", $tempDump)

Write-Host "Restaurando Qdrant..."
$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if (-not $curl) { throw "No se encuentra curl.exe, necesario para subir el snapshot a Qdrant." }
$url = "http://localhost:6333/collections/{0}/snapshots/upload?priority=snapshot&wait=true" -f $manifest.qdrant_collection
& curl.exe --fail --silent --show-error -X POST -F ("snapshot=@{0}" -f $qdrantFile) $url
if ($LASTEXITCODE -ne 0) { throw "Qdrant no ha podido recuperar el snapshot." }

if ($RestoreData) {
    $dataFile = Join-Path $resolved "data.zip"
    if (Test-Path $dataFile) {
        Expand-Archive -Path $dataFile -DestinationPath (Join-Path $Root "data") -Force
    }
}

Write-Host "Arrancando la aplicacion..."
Invoke-Compose -Arguments @("up", "-d", "api", "web")
Write-Host "Restauracion completada. Comprueba http://localhost:8000/health/dependencies" -ForegroundColor Green

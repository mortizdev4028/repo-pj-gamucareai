param(
    [string]$Destination = ".\backups",
    [switch]$IncludeLogs
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

function Invoke-Compose {
    param([string[]]$Arguments, [switch]$AllowFailure)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker compose @Compose @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previous }
    if ($code -ne 0 -and -not $AllowFailure) { throw ("docker compose ha fallado con codigo {0}: {1}" -f $code, ($Arguments -join " ")) }
    return $code
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

function Get-EnvValue {
    param([string]$Name, [string]$Default)
    if (Test-Path ".env") {
        $line = Get-Content ".env" | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -Last 1
        if ($line) { return ($line -split '=', 2)[1] }
    }
    return $Default
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$destinationPath = (Resolve-Path $Destination).Path
$backupPath = Join-Path $destinationPath ("gamucare-{0}" -f $timestamp)
New-Item -ItemType Directory -Force -Path $backupPath | Out-Null

$postgresUser = Get-EnvValue "POSTGRES_USER" "gamucare"
$postgresDb = Get-EnvValue "POSTGRES_DB" "gamucare"
$collection = Get-EnvValue "QDRANT_COLLECTION" "gamucare_knowledge"

Write-Host "Comprobando PostgreSQL y Qdrant..."
Invoke-Compose -Arguments @("up", "-d", "postgres", "qdrant") | Out-Null

Write-Host "Creando copia de PostgreSQL..."
$tempDump = "/tmp/gamucare-postgres.dump"
Invoke-Compose -Arguments @("exec", "-T", "postgres", "pg_dump", "-U", $postgresUser, "-d", $postgresDb, "-Fc", "-f", $tempDump) | Out-Null
$postgresFile = Join-Path $backupPath "postgres.dump"
Invoke-Docker -Arguments @("cp", ("gamucare-postgres:{0}" -f $tempDump), $postgresFile)
Invoke-Compose -Arguments @("exec", "-T", "postgres", "rm", "-f", $tempDump) -AllowFailure | Out-Null

Write-Host "Creando snapshot de Qdrant..."
$snapshotResponse = Invoke-RestMethod -Method Post -Uri ("http://localhost:6333/collections/{0}/snapshots" -f $collection) -TimeoutSec 120
$snapshotName = $snapshotResponse.result.name
if (-not $snapshotName) { throw "Qdrant no ha devuelto el nombre del snapshot." }
$qdrantFile = Join-Path $backupPath "qdrant.snapshot"
Invoke-WebRequest -Uri ("http://localhost:6333/collections/{0}/snapshots/{1}" -f $collection, $snapshotName) -OutFile $qdrantFile -UseBasicParsing -TimeoutSec 300

Write-Host "Archivando documentos, datasets e informes..."
$dataFile = Join-Path $backupPath "data.zip"
Compress-Archive -Path (Join-Path $Root "data\*") -DestinationPath $dataFile -CompressionLevel Optimal -Force

if ($IncludeLogs) {
    $logFile = Join-Path $backupPath "api.jsonl"
    Invoke-Docker -Arguments @("cp", "gamucare-api:/var/log/gamucare/api.jsonl", $logFile)
}

$versionLine = Get-Content (Join-Path $Root "backend\app\version.py") | Where-Object { $_ -match "APP_VERSION" } | Select-Object -First 1
$version = if ($versionLine -match "'([^']+)'" ) { $Matches[1] } else { "unknown" }
$files = Get-ChildItem $backupPath -File | ForEach-Object {
    [ordered]@{
        name = $_.Name
        size_bytes = $_.Length
        sha256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$manifest = [ordered]@{
    format_version = 1
    application_version = $version
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    postgres_database = $postgresDb
    postgres_user = $postgresUser
    qdrant_collection = $collection
    includes_ollama_models = $false
    files = @($files)
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $backupPath "manifest.json") -Encoding UTF8

Write-Host ("Backup completado: {0}" -f $backupPath) -ForegroundColor Green
Write-Host "Los modelos de Ollama no se incluyen; se pueden volver a descargar con setup-gpu.ps1."

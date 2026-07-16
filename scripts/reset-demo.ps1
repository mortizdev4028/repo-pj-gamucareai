param(
    [switch]$Force,
    [switch]$SkipRag,
    [switch]$SkipEvaluation,
    [switch]$SkipMonitoring,
    [switch]$WithGeneration
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure,
        [switch]$Quiet,
        [switch]$Monitoring
    )
    $base = @($Compose)
    if ($Monitoring) { $base += @("--profile", "monitoring") }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($Quiet) { & docker compose @base @Arguments *> $null }
        else { & docker compose @base @Arguments 2>&1 | ForEach-Object { Write-Host $_ } }
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previous }
    if ($code -ne 0 -and -not $AllowFailure) {
        throw ("docker compose ha fallado con codigo {0}: {1}" -f $code, ($Arguments -join " "))
    }
    return $code
}

function Get-EnvValue {
    param([string]$Name, [string]$Default)
    if (Test-Path ".env") {
        $line = Get-Content ".env" | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -Last 1
        if ($line) { return ($line -split '=', 2)[1] }
    }
    return $Default
}

function Wait-Http200 {
    param([string]$Uri, [int]$Attempts = 90)
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) { return $true }
        }
        catch { Start-Sleep -Seconds 3 }
    }
    return $false
}

if (-not $Force) {
    Write-Warning "Este proceso elimina y reconstruye todos los datos de PostgreSQL y la coleccion Qdrant de demostracion."
    Write-Host "Conserva los modelos de Ollama y los volumenes de monitorizacion."
    $answer = Read-Host "Escribe REINICIAR DEMO para continuar"
    if ($answer -ne "REINICIAR DEMO") {
        Write-Host "Operacion cancelada."
        exit 0
    }
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env desde .env.example"
}

Write-Host "Preparando imagenes y dependencias..." -ForegroundColor Cyan
Invoke-Compose -Arguments @("build", "api", "web") | Out-Null
Invoke-Compose -Arguments @("stop", "web", "api") -AllowFailure | Out-Null
Invoke-Compose -Arguments @("up", "-d", "postgres", "qdrant", "ollama") | Out-Null

$postgresUser = Get-EnvValue "POSTGRES_USER" "gamucare"
$postgresDb = Get-EnvValue "POSTGRES_DB" "gamucare"
$postgresReady = $false
for ($i = 1; $i -le 80; $i++) {
    $code = Invoke-Compose -Arguments @("exec", "-T", "postgres", "pg_isready", "-U", $postgresUser, "-d", $postgresDb) -Quiet -AllowFailure
    if ($code -eq 0) { $postgresReady = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $postgresReady) { throw "PostgreSQL no ha quedado disponible." }

Write-Host "Reconstruyendo el esquema PostgreSQL..." -ForegroundColor Cyan
$sql = "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
Invoke-Compose -Arguments @("exec", "-T", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", $postgresUser, "-d", $postgresDb, "-c", $sql) | Out-Null
Invoke-Compose -Arguments @("run", "--rm", "--no-deps", "--entrypoint", "alembic", "api", "upgrade", "head") | Out-Null

Write-Host "Cargando el dataset ficticio determinista..." -ForegroundColor Cyan
Invoke-Compose -Arguments @("run", "--rm", "--no-deps", "--entrypoint", "python", "api", "-m", "app.seed") | Out-Null
Invoke-Compose -Arguments @("run", "--rm", "--no-deps", "--entrypoint", "python", "api", "-m", "app.scripts.enrich_demo_histories") | Out-Null

if (-not $SkipRag) {
    Write-Host "Reconstruyendo Qdrant y los avisos preventivos..." -ForegroundColor Cyan
    Invoke-Compose -Arguments @("run", "--rm", "--no-deps", "--entrypoint", "python", "api", "-m", "app.rag.ingest") | Out-Null
    Invoke-Compose -Arguments @("run", "--rm", "--no-deps", "--entrypoint", "python", "api", "-m", "app.scripts.enrich_alerts") | Out-Null
}

Write-Host "Arrancando API y frontend..." -ForegroundColor Cyan
Invoke-Compose -Arguments @("up", "-d", "api", "web") | Out-Null
if (-not (Wait-Http200 -Uri "http://localhost:8000/health/live")) {
    Invoke-Compose -Arguments @("logs", "--tail=180", "api") -AllowFailure | Out-Null
    throw "La API no ha respondido tras reconstruir el entorno demo."
}

if (-not $SkipEvaluation) {
    Write-Host "Ejecutando evaluacion de VetIA..." -ForegroundColor Cyan
    $ragArgs = @("exec", "-T", "api", "python", "-m", "app.scripts.evaluate_rag")
    if ($WithGeneration) { $ragArgs += "--with-generation" }
    Invoke-Compose -Arguments $ragArgs | Out-Null

    Write-Host "Ejecutando validacion formal del MVP..." -ForegroundColor Cyan
    $evaluationCode = Invoke-Compose -Arguments @("exec", "-T", "api", "python", "-m", "app.scripts.evaluate_system", "--skip-vetia") -AllowFailure
    if ($evaluationCode -notin @(0, 3)) { throw ("La validacion formal ha fallado con codigo {0}." -f $evaluationCode) }
    if ($evaluationCode -eq 3) { Write-Warning "La validacion formal termino con criterios pendientes." }
}

Invoke-Compose -Arguments @("exec", "-T", "api", "python", "-m", "app.scripts.release_snapshot", "--output", "/app/data/reports/demo-snapshot-v0.16.0-rc1.json") | Out-Null

if (-not $SkipMonitoring) {
    Invoke-Compose -Arguments @("up", "-d", "postgres-exporter", "blackbox-exporter", "alertmanager", "prometheus", "grafana") -Monitoring | Out-Null
}

if (-not $SkipMonitoring) {
    & "$PSScriptRoot/smoke-test.ps1" -IncludeMonitoring
}
else {
    & "$PSScriptRoot/smoke-test.ps1"
}

Write-Host "Entorno de demostracion reconstruido." -ForegroundColor Green
Write-Host "Aplicacion: http://localhost:8080"
Write-Host "Contrasena comun: GamuCare123!"
Write-Host "Resumen: data/reports/demo-snapshot-v0.16.0-rc1.json"

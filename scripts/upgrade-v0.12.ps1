param(
    [switch]$SkipMonitoring,
    [switch]$SkipTests,
    [switch]$SkipEvaluation
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$Quiet,
        [switch]$AllowFailure,
        [switch]$Monitoring
    )
    $base = @($Compose)
    if ($Monitoring) { $base += @("--profile", "monitoring") }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($Quiet) {
            & docker compose @base @Arguments *> $null
        }
        else {
            & docker compose @base @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        }
        $exitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previous }
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw ("docker compose ha fallado con codigo {0}: {1}" -f $exitCode, ($Arguments -join " "))
    }
    return $exitCode
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
    param([string]$Uri, [int]$Attempts = 120, [int]$DelaySeconds = 3)
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) { return $true }
        }
        catch {
            if (($i % 10) -eq 0) { Write-Host ("Esperando {0} - intento {1} de {2}" -f $Uri, $i, $Attempts) }
        }
        Start-Sleep -Seconds $DelaySeconds
    }
    return $false
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env desde .env.example"
}

Write-Host "Construyendo GamuCare AI 0.12.0..."
Invoke-Compose -Arguments @("build", "api", "web") | Out-Null

Write-Host "Deteniendo temporalmente API y frontend..."
Invoke-Compose -Arguments @("stop", "web", "api") -AllowFailure | Out-Null

Write-Host "Arrancando PostgreSQL, Qdrant y Ollama..."
Invoke-Compose -Arguments @("up", "-d", "postgres", "qdrant", "ollama") | Out-Null

Write-Host "Esperando a PostgreSQL..."
$postgresUser = Get-EnvValue "POSTGRES_USER" "gamucare"
$postgresDb = Get-EnvValue "POSTGRES_DB" "gamucare"
$postgresReady = $false
for ($i = 1; $i -le 80; $i++) {
    $code = Invoke-Compose -Arguments @("exec", "-T", "postgres", "pg_isready", "-U", $postgresUser, "-d", $postgresDb) -Quiet -AllowFailure
    if ($code -eq 0) { $postgresReady = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $postgresReady) {
    Invoke-Compose -Arguments @("logs", "--tail=120", "postgres") -AllowFailure | Out-Null
    throw "PostgreSQL no ha quedado disponible."
}

Write-Host "Aplicando migraciones existentes..."
Invoke-Compose -Arguments @("run", "--rm", "--no-deps", "--entrypoint", "alembic", "api", "upgrade", "head") | Out-Null

Write-Host "Arrancando API y frontend..."
Invoke-Compose -Arguments @("up", "-d", "api", "web") | Out-Null

if (-not (Wait-Http200 -Uri "http://localhost:8000/health/live")) {
    Invoke-Compose -Arguments @("logs", "--tail=180", "api") -AllowFailure | Out-Null
    throw "La API no ha respondido en /health/live."
}
if (-not (Wait-Http200 -Uri "http://localhost:8000/health/ready" -Attempts 30)) {
    Invoke-Compose -Arguments @("logs", "--tail=180", "api") -AllowFailure | Out-Null
    throw "La API esta viva, pero PostgreSQL no esta preparado."
}

Write-Host "Version de migracion aplicada:"
Invoke-Compose -Arguments @("exec", "-T", "api", "alembic", "current") | Out-Null

if (-not $SkipTests) {
    Write-Host "Ejecutando pruebas del backend..."
    Invoke-Compose -Arguments @("exec", "-T", "api", "python", "-m", "pytest", "-q", "/app/tests") | Out-Null
}

if (-not $SkipEvaluation) {
    Write-Host "Ejecutando validacion formal sin VetIA..."
    $evaluationCode = Invoke-Compose -Arguments @("exec", "-T", "api", "python", "-m", "app.scripts.evaluate_system", "--skip-vetia") -AllowFailure
    if ($evaluationCode -eq 0) {
        Write-Host "Validacion formal completada."
    }
    elseif ($evaluationCode -eq 3) {
        Write-Warning "La validacion ha terminado con criterios pendientes. Consulta Validacion del MVP para ver el detalle."
    }
    else {
        throw ("La validacion formal no ha podido ejecutarse. Codigo: {0}" -f $evaluationCode)
    }
}

if (-not $SkipMonitoring) {
    Write-Host "Arrancando Prometheus, Grafana, Alertmanager y exporters..."
    Invoke-Compose -Arguments @("up", "-d", "postgres-exporter", "blackbox-exporter", "alertmanager", "prometheus", "grafana") -Monitoring | Out-Null
}

Write-Host "Actualizacion 0.12.0 completada." -ForegroundColor Green
Write-Host "Aplicacion:        http://localhost:8080"
Write-Host "Estado tecnico:    http://localhost:8080/system-status"
Write-Host "Grafana:           http://localhost:3000"
Write-Host "Prometheus:        http://localhost:9090"
Write-Host "Alertmanager:      http://localhost:9093"
Write-Host "Backup manual:     .\scripts\backup.ps1"

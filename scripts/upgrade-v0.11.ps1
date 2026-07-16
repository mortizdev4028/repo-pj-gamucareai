$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$Quiet,
        [switch]$AllowFailure
    )

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($Quiet) {
            & docker compose @Compose @Arguments *> $null
        }
        else {
            & docker compose @Compose @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        }
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }

    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "docker compose ha fallado con codigo $exitCode: $($Arguments -join ' ')"
    }
    return $exitCode
}


function Get-EnvValue {
    param([string]$Name)
    if (-not (Test-Path ".env")) { return $null }
    $line = Get-Content ".env" | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -Last 1
    if (-not $line) { return $null }
    return ($line -split '=', 2)[1]
}

function Wait-Http200 {
    param(
        [string]$Uri,
        [int]$Attempts = 120,
        [int]$DelaySeconds = 3
    )

    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) { return $true }
        }
        catch {
            if (($i % 10) -eq 0) {
                Write-Host "Esperando $Uri - intento $i de $Attempts"
            }
        }
        Start-Sleep -Seconds $DelaySeconds
    }
    return $false
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env desde .env.example"
}

Write-Host "Construyendo GamuCare AI 0.11.0..."
Invoke-Compose -Arguments @("build", "api", "web") | Out-Null

Write-Host "Deteniendo temporalmente API y frontend..."
Invoke-Compose -Arguments @("stop", "web", "api") | Out-Null

Write-Host "Arrancando PostgreSQL, Qdrant y Ollama..."
Invoke-Compose -Arguments @("up", "-d", "postgres", "qdrant", "ollama") | Out-Null

Write-Host "Esperando a PostgreSQL..."
$PostgresUser = Get-EnvValue "POSTGRES_USER"
if (-not $PostgresUser) { $PostgresUser = "gamucare" }
$PostgresDb = Get-EnvValue "POSTGRES_DB"
if (-not $PostgresDb) { $PostgresDb = "gamucare" }
$postgresReady = $false
for ($i = 1; $i -le 80; $i++) {
    $code = Invoke-Compose -Arguments @("exec", "-T", "postgres", "pg_isready", "-U", $PostgresUser, "-d", $PostgresDb) -Quiet -AllowFailure
    if ($code -eq 0) {
        $postgresReady = $true
        break
    }
    Start-Sleep -Seconds 3
}
if (-not $postgresReady) {
    Invoke-Compose -Arguments @("logs", "--tail=120", "postgres") -AllowFailure | Out-Null
    throw "PostgreSQL no ha quedado disponible."
}

Write-Host "Aplicando migraciones hasta 0009_system_evaluation..."
Invoke-Compose -Arguments @("run", "--rm", "--no-deps", "--entrypoint", "alembic", "api", "upgrade", "head") | Out-Null

Write-Host "Arrancando API y frontend..."
Invoke-Compose -Arguments @("up", "-d", "api", "web") | Out-Null

Write-Host "Esperando a la API en /health/live..."
if (-not (Wait-Http200 -Uri "http://localhost:8000/health/live")) {
    Invoke-Compose -Arguments @("ps") -AllowFailure | Out-Null
    Invoke-Compose -Arguments @("logs", "--tail=180", "api") -AllowFailure | Out-Null
    throw "La API no ha respondido dentro del tiempo esperado."
}

Write-Host "Comprobando /health/ready..."
if (-not (Wait-Http200 -Uri "http://localhost:8000/health/ready" -Attempts 20 -DelaySeconds 3)) {
    Invoke-Compose -Arguments @("logs", "--tail=180", "api") -AllowFailure | Out-Null
    throw "La API esta viva, pero PostgreSQL no esta preparado."
}

Write-Host "Version de migracion aplicada:"
Invoke-Compose -Arguments @("exec", "-T", "api", "alembic", "current") | Out-Null

Write-Host "Ejecutando la evaluacion formal inicial..."
Write-Host "La evaluacion ejecuta pytest, cobertura, criterios de aceptacion, avisos y un benchmark corto."
Invoke-Compose -Arguments @("exec", "-T", "api", "python", "-m", "app.scripts.evaluate_system", "--skip-vetia") | Out-Null

Write-Host "Actualizacion 0.11.0 completada."
Write-Host "Aplicacion:        http://localhost:8080"
Write-Host "VetIA:             http://localhost:8080/chat"
Write-Host "Calidad de VetIA:  http://localhost:8080/vetia-quality"
Write-Host "Validacion MVP:    http://localhost:8080/quality"
Write-Host "Los volumenes y datos anteriores se han conservado."

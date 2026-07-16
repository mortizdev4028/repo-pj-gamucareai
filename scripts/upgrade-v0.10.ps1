$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Set-EnvValue {
    param([string]$Name, [string]$Value)
    $lines = if (Test-Path ".env") { Get-Content ".env" } else { @() }
    $pattern = "^$([regex]::Escape($Name))="
    $found = $false
    $updated = foreach ($line in $lines) {
        if ($line -match $pattern) {
            $found = $true
            "$Name=$Value"
        } else {
            $line
        }
    }
    if (-not $found) { $updated += "$Name=$Value" }
    [System.IO.File]::WriteAllLines((Join-Path $Root ".env"), $updated, (New-Object System.Text.UTF8Encoding($false)))
}

function Get-EnvValue {
    param([string]$Name)
    if (-not (Test-Path ".env")) { return $null }
    $line = Get-Content ".env" | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -Last 1
    if (-not $line) { return $null }
    return ($line -split '=', 2)[1]
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env desde .env.example"
}

# Preserve existing values and add only the settings introduced in v0.10.0.
$securityDefaults = @{
    ACCESS_TOKEN_EXPIRE_MINUTES = "30"
    REFRESH_TOKEN_EXPIRE_DAYS = "7"
    REFRESH_COOKIE_NAME = "gamucare_refresh"
    REFRESH_COOKIE_SECURE = "false"
    REFRESH_COOKIE_SAMESITE = "lax"
    MAX_FAILED_LOGIN_ATTEMPTS = "5"
    LOGIN_LOCK_MINUTES = "15"
    PASSWORD_MIN_LENGTH = "12"
}
foreach ($entry in $securityDefaults.GetEnumerator()) {
    if (-not (Get-EnvValue $entry.Key)) { Set-EnvValue $entry.Key $entry.Value }
}

$jwtSecret = Get-EnvValue "JWT_SECRET"
if (-not $jwtSecret -or $jwtSecret -eq "change-this-local-secret-before-production" -or $jwtSecret.Length -lt 32) {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    $generatedSecret = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    Set-EnvValue "JWT_SECRET" $generatedSecret
    Write-Host "JWT_SECRET local generado y guardado en .env"
    Write-Warning "Las sesiones JWT anteriores dejaran de ser validas. Los datos de negocio no se modifican."
}

Write-Warning "El nuevo formato de sesion obliga a iniciar sesion de nuevo tras la actualizacion."

$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

Write-Host "Construyendo GamuCare AI 0.10.0..."
docker compose @Compose build api web
if ($LASTEXITCODE -ne 0) { throw "La construccion de las imagenes ha fallado." }

Write-Host "Deteniendo temporalmente API y frontend para aplicar la migracion de forma consistente..."
$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"

try {
    & docker compose @Compose stop web api 2>&1 |
        ForEach-Object { Write-Host $_ }

    $dockerExitCode = $LASTEXITCODE

    if ($dockerExitCode -ne 0) {
        throw "No se pudieron detener API y frontend. Código: $dockerExitCode"
    }
}
finally {
    $ErrorActionPreference = $previousErrorAction
}

Write-Host "Arrancando dependencias..."
docker compose @Compose up -d postgres qdrant ollama
if ($LASTEXITCODE -ne 0) { throw "No se han podido arrancar las dependencias." }

Write-Host "Esperando a PostgreSQL..."
$PostgresUser = Get-EnvValue "POSTGRES_USER"
if (-not $PostgresUser) { $PostgresUser = "gamucare" }
$PostgresDb = Get-EnvValue "POSTGRES_DB"
if (-not $PostgresDb) { $PostgresDb = "gamucare" }
$PostgresReady = $false
for ($i = 1; $i -le 80; $i++) {
    docker compose @Compose exec -T postgres pg_isready -U $PostgresUser -d $PostgresDb *> $null
    if ($LASTEXITCODE -eq 0) { $PostgresReady = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $PostgresReady) {
    docker compose @Compose logs --tail=100 postgres
    throw "PostgreSQL no ha quedado disponible dentro del tiempo esperado."
}

Write-Host "Aplicando la migracion 0008_security_audit antes de arrancar la API..."
docker compose @Compose run --rm --no-deps --entrypoint alembic api upgrade head
if ($LASTEXITCODE -ne 0) { throw "Alembic no ha podido aplicar las migraciones." }

Write-Host "Arrancando API y frontend..."
docker compose @Compose up -d api web
if ($LASTEXITCODE -ne 0) { throw "No se han podido arrancar la API y el frontend." }

Write-Host "Esperando a la API en /health/live..."
$ApiLive = $false
for ($i = 1; $i -le 120; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health/live" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) { $ApiLive = $true; break }
    } catch {
        if (($i % 10) -eq 0) { Write-Host "La API sigue arrancando: intento $i de 120" }
    }
    Start-Sleep -Seconds 3
}
if (-not $ApiLive) {
    docker compose @Compose ps
    docker compose @Compose logs --tail=150 api
    throw "La API no ha respondido en /health/live dentro del tiempo esperado."
}

Write-Host "Comprobando disponibilidad de PostgreSQL desde /health/ready..."
try {
    $ready = Invoke-WebRequest -Uri "http://localhost:8000/health/ready" -UseBasicParsing -TimeoutSec 10
    if ($ready.StatusCode -ne 200) { throw "Estado inesperado: $($ready.StatusCode)" }
} catch {
    docker compose @Compose logs --tail=150 api
    throw "La API esta viva, pero no esta preparada para acceder a PostgreSQL: $($_.Exception.Message)"
}

Write-Host "Version de migracion aplicada:"
docker compose @Compose exec -T api alembic current

Write-Host "Ejecutando pruebas del backend..."
docker compose @Compose exec -T api pytest -q
if ($LASTEXITCODE -ne 0) { throw "Las pruebas del backend han fallado." }

Write-Host "Actualizacion 0.10.0 completada."
Write-Host "Aplicacion: http://localhost:8080"
Write-Host "Auditoria:  http://localhost:8080/audit"
Write-Host "Seguridad:  http://localhost:8080/security"
Write-Host "Los volumenes y datos anteriores se han conservado."

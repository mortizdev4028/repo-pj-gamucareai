param(
    [switch]$SkipQdrant,
    [switch]$SkipOllama,
    [int]$RecoveryTimeoutSeconds = 120
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
    if ($code -ne 0 -and -not $AllowFailure) {
        throw ("docker compose ha fallado con codigo {0}: {1}" -f $code, ($Arguments -join ' '))
    }
    return $code
}

function Get-DependencyState {
    param([string]$Name)
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health/dependencies" -UseBasicParsing -TimeoutSec 10
        $payload = $response.Content | ConvertFrom-Json
        return @{ Http = [int]$response.StatusCode; State = $payload.dependencies.$Name.status }
    }
    catch {
        $http = 0
        try { $http = [int]$_.Exception.Response.StatusCode.value__ } catch { }
        $body = $_.ErrorDetails.Message
        if (-not $body -and $_.Exception.Response) {
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $body = $reader.ReadToEnd()
                $reader.Dispose()
            }
            catch { }
        }
        if ($body) {
            try {
                $payload = $body | ConvertFrom-Json
                return @{ Http = $http; State = $payload.dependencies.$Name.status }
            }
            catch { }
        }
        return @{ Http = $http; State = 'unknown' }
    }
}

function Wait-Dependency {
    param([string]$Name, [string]$Expected, [int]$TimeoutSeconds)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $state = Get-DependencyState $Name
        if ($state.State -eq $Expected) {
            Write-Host ("[OK] {0}={1}; health HTTP {2}" -f $Name, $Expected, $state.Http) -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $deadline)
    throw ("No se alcanzo el estado {0} para {1}. Ultimo estado: {2}, HTTP {3}" -f $Expected, $Name, $state.State, $state.Http)
}

function Test-ServiceFailure {
    param([string]$Service, [string]$Dependency)
    Write-Host ("Deteniendo temporalmente {0}..." -f $Service) -ForegroundColor Yellow
    try {
        Invoke-Compose -Arguments @('stop', $Service) | Out-Null
        Wait-Dependency -Name $Dependency -Expected 'down' -TimeoutSeconds 45
    }
    finally {
        Write-Host ("Recuperando {0}..." -f $Service) -ForegroundColor Yellow
        Invoke-Compose -Arguments @('start', $Service) -AllowFailure | Out-Null
    }
    Wait-Dependency -Name $Dependency -Expected 'up' -TimeoutSeconds $RecoveryTimeoutSeconds
}

Write-Host "Prueba controlada de resiliencia. Los datos y volumenes no se eliminan." -ForegroundColor Cyan
if (-not $SkipQdrant) { Test-ServiceFailure -Service 'qdrant' -Dependency 'qdrant' }
if (-not $SkipOllama) { Test-ServiceFailure -Service 'ollama' -Dependency 'ollama' }
Write-Host "Pruebas de resiliencia completadas y servicios recuperados." -ForegroundColor Green

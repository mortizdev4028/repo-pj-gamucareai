param(
    [switch]$SkipMonitoring,
    [switch]$SkipTests,
    [switch]$SkipEvaluation,
    [switch]$SkipRagReindex,
    [switch]$DownloadSources,
    [switch]$ResetDemo,
    [switch]$GenerateEvidence
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")

function Invoke-Compose {
    param([string[]]$Arguments, [switch]$AllowFailure, [switch]$Monitoring)
    $base = @($Compose)
    if ($Monitoring) { $base += @("--profile", "monitoring") }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker compose @base @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previous }
    if ($code -ne 0 -and -not $AllowFailure) {
        throw ("docker compose ha fallado con codigo {0}: {1}" -f $code, ($Arguments -join " "))
    }
    return $code
}

function Wait-Http200 {
    param([string]$Uri, [int]$Attempts = 120)
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) { return $true }
        }
        catch { Start-Sleep -Seconds 3 }
    }
    return $false
}

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host "Construyendo GamuCare AI 0.16.0-rc1..." -ForegroundColor Cyan
Invoke-Compose -Arguments @("build", "api", "web") | Out-Null
Invoke-Compose -Arguments @("stop", "web", "api") -AllowFailure | Out-Null
Invoke-Compose -Arguments @("up", "-d", "postgres", "qdrant", "ollama") | Out-Null
Invoke-Compose -Arguments @("run", "--rm", "--no-deps", "--entrypoint", "alembic", "api", "upgrade", "head") | Out-Null
Invoke-Compose -Arguments @("up", "-d", "api", "web") | Out-Null

if (-not (Wait-Http200 -Uri "http://localhost:8000/health/live")) {
    Invoke-Compose -Arguments @("logs", "--tail=180", "api") -AllowFailure | Out-Null
    throw "La API no ha respondido en /health/live."
}

if ($DownloadSources) {
    Invoke-Compose -Arguments @("exec", "-T", "api", "python", "-m", "app.scripts.download_rag_sources") | Out-Null
}
if (-not $SkipRagReindex) {
    Invoke-Compose -Arguments @("exec", "-T", "api", "python", "-m", "app.rag.ingest") | Out-Null
}
if (-not $SkipTests) {
    Invoke-Compose -Arguments @("exec", "-T", "api", "python", "-m", "pytest", "-q", "/app/tests") | Out-Null
}
if (-not $SkipEvaluation) {
    $evaluationCode = Invoke-Compose -Arguments @("exec", "-T", "api", "python", "-m", "app.scripts.evaluate_system", "--skip-vetia") -AllowFailure
    if ($evaluationCode -notin @(0, 3)) { throw ("Evaluacion fallida con codigo {0}." -f $evaluationCode) }
    if ($evaluationCode -eq 3) { Write-Warning "La evaluacion termino con criterios pendientes." }
}
if (-not $SkipMonitoring) {
    Invoke-Compose -Arguments @("up", "-d", "postgres-exporter", "blackbox-exporter", "alertmanager", "prometheus", "grafana") -Monitoring | Out-Null
}

if ($ResetDemo) {
    if ($SkipMonitoring -and $SkipEvaluation) { & "$PSScriptRoot/reset-demo.ps1" -Force -SkipMonitoring -SkipEvaluation }
    elseif ($SkipMonitoring) { & "$PSScriptRoot/reset-demo.ps1" -Force -SkipMonitoring }
    elseif ($SkipEvaluation) { & "$PSScriptRoot/reset-demo.ps1" -Force -SkipEvaluation }
    else { & "$PSScriptRoot/reset-demo.ps1" -Force }
}
if ($GenerateEvidence) {
    if ($SkipMonitoring) { & "$PSScriptRoot/generate-evidence.ps1" }
    else { & "$PSScriptRoot/generate-evidence.ps1" -IncludeMonitoring }
}

Write-Host "Actualizacion 0.16.0-rc1 completada." -ForegroundColor Green
Write-Host "Aplicacion:       http://localhost:8080"
Write-Host "Reinicio demo:    .\scripts\reset-demo.ps1"
Write-Host "Evidencias:       .\scripts\generate-evidence.ps1 -IncludeMonitoring -IncludePermissions"
Write-Host "Guion de demo:    docs/DEMO_GUIDE.md"
Write-Host "Lista de entrega: docs/DELIVERY_CHECKLIST.md"

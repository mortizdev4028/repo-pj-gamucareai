param(
    [switch]$SkipTests,
    [switch]$SkipPermissions,
    [switch]$SkipEvaluation,
    [switch]$IncludeResilience,
    [switch]$IncludeBackup,
    [switch]$IncludeMonitoring
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

Write-Host "1/6 Smoke test" -ForegroundColor Cyan
if ($IncludeMonitoring) { & "$PSScriptRoot/smoke-test.ps1" -IncludeMonitoring }
else { & "$PSScriptRoot/smoke-test.ps1" }

if (-not $SkipPermissions) {
    Write-Host "2/6 Matriz de permisos" -ForegroundColor Cyan
    & "$PSScriptRoot/test-permissions.ps1"
}

if (-not $SkipTests) {
    Write-Host "3/6 Pruebas backend" -ForegroundColor Cyan
    Invoke-Compose -Arguments @('exec', '-T', 'api', 'python', '-m', 'pytest', '-q', '/app/tests') | Out-Null
}

if (-not $SkipEvaluation) {
    Write-Host "4/6 Validacion formal del MVP" -ForegroundColor Cyan
    $code = Invoke-Compose -Arguments @('exec', '-T', 'api', 'python', '-m', 'app.scripts.evaluate_system', '--skip-vetia') -AllowFailure
    if ($code -notin @(0, 3)) { throw ("La validacion formal no ha podido ejecutarse. Codigo {0}" -f $code) }
    if ($code -eq 3) { Write-Warning "La evaluacion termino con criterios pendientes; revisa la pantalla Validacion del MVP." }
}

if ($IncludeResilience) {
    Write-Host "5/6 Resiliencia de Qdrant y Ollama" -ForegroundColor Cyan
    & "$PSScriptRoot/resilience-test.ps1"
}

if ($IncludeBackup) {
    Write-Host "6/6 Backup y verificacion" -ForegroundColor Cyan
    $before = @(Get-ChildItem "$Root/backups" -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime)
    & "$PSScriptRoot/backup.ps1"
    $after = @(Get-ChildItem "$Root/backups" -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime)
    $latest = $after | Select-Object -Last 1
    if (-not $latest -or ($before.Count -eq $after.Count -and $before[-1].FullName -eq $latest.FullName)) {
        throw "No se ha podido identificar el backup recien creado."
    }
    & "$PSScriptRoot/verify-backup.ps1" -BackupPath $latest.FullName
}

Write-Host "Validacion de release completada." -ForegroundColor Green

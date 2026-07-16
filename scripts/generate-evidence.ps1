param(
    [switch]$IncludeMonitoring,
    [switch]$IncludePermissions,
    [switch]$IncludeResilience,
    [switch]$IncludeBackup,
    [switch]$WithGeneration,
    [string]$OutputRoot = "evidence"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$EvidenceDir = Join-Path $Root (Join-Path $OutputRoot ("gamucare-v0.16.0-rc1-{0}" -f $Stamp))
New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null

function Invoke-ComposeCapture {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$OutputFile,
        [switch]$AllowCode3,
        [switch]$Monitoring
    )
    $base = @($Compose)
    if ($Monitoring) { $base += @("--profile", "monitoring") }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker compose @base @Arguments 2>&1 | Tee-Object -FilePath $OutputFile | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previous }
    $allowed = if ($AllowCode3) { @(0, 3) } else { @(0) }
    if ($code -notin $allowed) {
        throw ("Comando Compose fallido ({0}): {1}" -f $code, ($Arguments -join " "))
    }
    return $code
}

function Save-WebJson {
    param([string]$Uri, [string]$Path)
    $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 15
    [System.IO.File]::WriteAllText($Path, $response.Content, (New-Object System.Text.UTF8Encoding($false)))
}

Write-Host "Generando evidencias en $EvidenceDir" -ForegroundColor Cyan

Invoke-ComposeCapture -Arguments @("ps", "--format", "json") -OutputFile (Join-Path $EvidenceDir "compose-status.jsonl") | Out-Null
Save-WebJson -Uri "http://localhost:8000/health/live" -Path (Join-Path $EvidenceDir "health-live.json")
Save-WebJson -Uri "http://localhost:8000/health/dependencies" -Path (Join-Path $EvidenceDir "health-dependencies.json")

$junitName = "junit-evidence-$Stamp.xml"
$coverageName = "coverage-evidence-$Stamp.json"
Invoke-ComposeCapture -Arguments @(
    "exec", "-T", "api", "python", "-m", "pytest", "-q", "/app/tests",
    "--junitxml=/app/data/reports/$junitName", "--cov=app", "--cov-report=json:/app/data/reports/$coverageName", "--cov-report=term-missing"
) -OutputFile (Join-Path $EvidenceDir "backend-tests.txt") | Out-Null

$hostJunit = Join-Path $Root ("data/reports/$junitName")
$hostCoverage = Join-Path $Root ("data/reports/$coverageName")
if (Test-Path $hostJunit) { Copy-Item $hostJunit (Join-Path $EvidenceDir "junit.xml") }
if (Test-Path $hostCoverage) { Copy-Item $hostCoverage (Join-Path $EvidenceDir "coverage.json") }

$ragArguments = @("exec", "-T", "api", "python", "-m", "app.scripts.evaluate_rag")
if ($WithGeneration) { $ragArguments += "--with-generation" }
Invoke-ComposeCapture -Arguments $ragArguments -OutputFile (Join-Path $EvidenceDir "vetia-quality.txt") | Out-Null

Invoke-ComposeCapture -Arguments @("exec", "-T", "api", "python", "-m", "app.scripts.evaluate_system", "--skip-vetia") -OutputFile (Join-Path $EvidenceDir "mvp-validation.txt") -AllowCode3 | Out-Null
Invoke-ComposeCapture -Arguments @("exec", "-T", "api", "python", "-m", "app.scripts.release_snapshot") -OutputFile (Join-Path $EvidenceDir "release-snapshot.json") | Out-Null

if ($IncludePermissions) {
    & "$PSScriptRoot/test-permissions.ps1" 2>&1 | Tee-Object -FilePath (Join-Path $EvidenceDir "permission-matrix.txt") | ForEach-Object { Write-Host $_ }
}

if ($IncludeMonitoring) {
    Save-WebJson -Uri "http://localhost:9090/api/v1/targets" -Path (Join-Path $EvidenceDir "prometheus-targets.json")
    Save-WebJson -Uri "http://localhost:9090/api/v1/alerts" -Path (Join-Path $EvidenceDir "prometheus-alerts.json")
    Save-WebJson -Uri "http://localhost:9093/api/v2/status" -Path (Join-Path $EvidenceDir "alertmanager-status.json")
}

if ($IncludeResilience) {
    & "$PSScriptRoot/resilience-test.ps1" 2>&1 | Tee-Object -FilePath (Join-Path $EvidenceDir "resilience-test.txt") | ForEach-Object { Write-Host $_ }
}

if ($IncludeBackup) {
    & "$PSScriptRoot/backup.ps1" 2>&1 | Tee-Object -FilePath (Join-Path $EvidenceDir "backup.txt") | ForEach-Object { Write-Host $_ }
    $latest = Get-ChildItem (Join-Path $Root "backups") -Directory | Sort-Object LastWriteTime | Select-Object -Last 1
    if (-not $latest) { throw "No se ha encontrado el backup generado." }
    & "$PSScriptRoot/verify-backup.ps1" -BackupPath $latest.FullName 2>&1 | Tee-Object -FilePath (Join-Path $EvidenceDir "backup-verification.txt") | ForEach-Object { Write-Host $_ }
}

$mode = if ($WithGeneration) { "generation" } else { "retrieval" }
$summary = @"
# Evidencias GamuCare AI v0.16.0-rc1

- Generadas: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")
- Modo de Calidad de VetIA: $mode
- Monitorizacion incluida: $IncludeMonitoring
- Matriz de permisos incluida: $IncludePermissions
- Resiliencia incluida: $IncludeResilience
- Backup incluido: $IncludeBackup

## Alcance

Candidato de entrega local con Docker Compose. AWS esta excluido. Los datos son ficticios y VetIA no sustituye el criterio veterinario.

## Archivos

Los resultados detallados, la cobertura, el estado de dependencias y el resumen agregado se encuentran en esta carpeta. `files.sha256` permite comprobar su integridad.
"@
[System.IO.File]::WriteAllText((Join-Path $EvidenceDir "release-summary.md"), $summary, (New-Object System.Text.UTF8Encoding($false)))

$hashLines = Get-ChildItem $EvidenceDir -File | Where-Object { $_.Name -ne "files.sha256" } | Sort-Object Name | ForEach-Object {
    $hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "{0}  {1}" -f $hash, $_.Name
}
[System.IO.File]::WriteAllLines((Join-Path $EvidenceDir "files.sha256"), $hashLines, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "Evidencias generadas: $EvidenceDir" -ForegroundColor Green

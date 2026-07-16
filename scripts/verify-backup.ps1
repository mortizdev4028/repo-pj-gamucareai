param([Parameter(Mandatory = $true)][string]$BackupPath)

$ErrorActionPreference = "Stop"
$resolved = (Resolve-Path $BackupPath).Path
$manifestPath = Join-Path $resolved "manifest.json"
if (-not (Test-Path $manifestPath)) { throw "No existe manifest.json en el backup." }
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$failed = 0
foreach ($entry in $manifest.files) {
    $filePath = Join-Path $resolved $entry.name
    if (-not (Test-Path $filePath)) {
        Write-Host ("[ERROR] Falta {0}" -f $entry.name) -ForegroundColor Red
        $failed += 1
        continue
    }
    $hash = (Get-FileHash $filePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $entry.sha256) {
        Write-Host ("[ERROR] Hash incorrecto: {0}" -f $entry.name) -ForegroundColor Red
        $failed += 1
    }
    else {
        Write-Host ("[OK] {0}" -f $entry.name) -ForegroundColor Green
    }
}
if ($failed -gt 0) { throw ("Backup invalido: {0} errores." -f $failed) }
Write-Host "Backup verificado correctamente." -ForegroundColor Green

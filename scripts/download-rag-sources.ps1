param(
    [switch]$Force,
    [switch]$Reindex
)

$ErrorActionPreference = 'Stop'
$compose = @('-f', 'docker-compose.yml')
if (Test-Path 'docker-compose.gpu.yml') {
    $compose += @('-f', 'docker-compose.gpu.yml')
}

function Invoke-DockerCompose {
    param([string[]]$Arguments)
    $output = & docker compose @compose @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $output | ForEach-Object { Write-Host $_ }
    if ($exitCode -ne 0) {
        throw ('docker compose fallo con codigo {0}' -f $exitCode)
    }
}

$downloadArgs = @('exec', '-T', 'api', 'python', '-m', 'app.scripts.download_rag_sources')
if ($Force) { $downloadArgs += '--force' }

Write-Host 'Descargando fuentes oficiales definidas en data/rag_sources/sources.json...'
Invoke-DockerCompose -Arguments $downloadArgs

if ($Reindex) {
    Write-Host 'Reconstruyendo la coleccion de Qdrant...'
    Invoke-DockerCompose -Arguments @('exec', '-T', 'api', 'python', '-m', 'app.rag.ingest')
}
else {
    Write-Host 'Descarga completada. Ejecute de nuevo con -Reindex para indexar los documentos.'
}

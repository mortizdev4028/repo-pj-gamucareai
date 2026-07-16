param([switch]$IncludeMonitoring)

$ErrorActionPreference = "Stop"
$checks = @(
    @{ Name = "Aplicacion web"; Uri = "http://localhost:8080" },
    @{ Name = "API live"; Uri = "http://localhost:8000/health/live" },
    @{ Name = "API ready"; Uri = "http://localhost:8000/health/ready" },
    @{ Name = "Dependencias"; Uri = "http://localhost:8000/health/dependencies" },
    @{ Name = "Qdrant"; Uri = "http://localhost:6333/readyz" },
    @{ Name = "Ollama"; Uri = "http://localhost:11434/api/tags" }
)
if ($IncludeMonitoring) {
    $checks += @(
        @{ Name = "Prometheus"; Uri = "http://localhost:9090/-/ready" },
        @{ Name = "Grafana"; Uri = "http://localhost:3000/api/health" },
        @{ Name = "Alertmanager"; Uri = "http://localhost:9093/-/ready" }
    )
}

$failed = 0
foreach ($check in $checks) {
    try {
        $response = Invoke-WebRequest -Uri $check.Uri -UseBasicParsing -TimeoutSec 10
        Write-Host ("[OK] {0} - HTTP {1}" -f $check.Name, $response.StatusCode) -ForegroundColor Green
    }
    catch {
        $failed += 1
        Write-Host ("[ERROR] {0} - {1}" -f $check.Name, $_.Exception.Message) -ForegroundColor Red
    }
}
if ($failed -gt 0) { throw ("Smoke test con {0} comprobaciones fallidas." -f $failed) }
Write-Host "Smoke test completado." -ForegroundColor Green

param(
    [string]$ApiBaseUrl = "http://localhost:8000/api/v1",
    [string]$Password = "GamuCare123!"
)

$ErrorActionPreference = "Stop"
$ApiBaseUrl = $ApiBaseUrl.TrimEnd('/')

function Get-StatusCodeFromError {
    param($ErrorRecord)
    try { return [int]$ErrorRecord.Exception.Response.StatusCode.value__ } catch { return 0 }
}

function Get-Token {
    param([string]$Email)
    $body = @{ email = $Email; password = $Password } | ConvertTo-Json
    try {
        $response = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/auth/login" -ContentType "application/json" -Body $body -TimeoutSec 20
        return $response.access_token
    }
    catch {
        throw ("No se pudo iniciar sesion como {0}: {1}" -f $Email, $_.Exception.Message)
    }
}

function Test-Endpoint {
    param(
        [string]$Role,
        [string]$Token,
        [string]$Path,
        [int[]]$Expected
    )
    $headers = @{ Authorization = "Bearer $Token"; "X-Request-ID" = "matrix-$Role-$([guid]::NewGuid().ToString('N').Substring(0,8))" }
    $statusCode = 0
    try {
        $response = Invoke-WebRequest -Method Get -Uri "$ApiBaseUrl$Path" -Headers $headers -UseBasicParsing -TimeoutSec 30
        $statusCode = [int]$response.StatusCode
    }
    catch {
        $statusCode = Get-StatusCodeFromError $_
        if ($statusCode -eq 0) { throw }
    }
    $ok = $Expected -contains $statusCode
    $label = if ($ok) { "OK" } else { "ERROR" }
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host ("[{0}] {1,-10} {2,-38} HTTP {3} esperado {4}" -f $label, $Role, $Path, $statusCode, ($Expected -join '/')) -ForegroundColor $color
    return $ok
}

$accounts = @{
    clinic = "clinic@gamucare.local"
    staff = "staff@gamucare.local"
    owner = "owner01@example.test"
    technical = "technical@gamucare.local"
}

$matrix = @(
    @{ Role = 'clinic'; Path = '/dashboard'; Expected = @(200) },
    @{ Role = 'clinic'; Path = '/owners?limit=1'; Expected = @(200) },
    @{ Role = 'clinic'; Path = '/alerts?limit=1'; Expected = @(200) },
    @{ Role = 'clinic'; Path = '/quality/status'; Expected = @(403) },
    @{ Role = 'clinic'; Path = '/observability/status'; Expected = @(403) },

    @{ Role = 'staff'; Path = '/dashboard'; Expected = @(200) },
    @{ Role = 'staff'; Path = '/owners?limit=1'; Expected = @(200) },
    @{ Role = 'staff'; Path = '/alerts?limit=1'; Expected = @(200) },
    @{ Role = 'staff'; Path = '/quality/status'; Expected = @(403) },
    @{ Role = 'staff'; Path = '/integrations/wakyma/status'; Expected = @(403) },

    @{ Role = 'owner'; Path = '/dashboard'; Expected = @(200) },
    @{ Role = 'owner'; Path = '/pets?limit=1'; Expected = @(200) },
    @{ Role = 'owner'; Path = '/owners?limit=1'; Expected = @(403) },
    @{ Role = 'owner'; Path = '/alerts?limit=1'; Expected = @(403) },
    @{ Role = 'owner'; Path = '/quality/status'; Expected = @(403) },

    @{ Role = 'technical'; Path = '/observability/status'; Expected = @(200, 503) },
    @{ Role = 'technical'; Path = '/quality/status'; Expected = @(200) },
    @{ Role = 'technical'; Path = '/rag/status'; Expected = @(200) },
    @{ Role = 'technical'; Path = '/integrations/wakyma/status'; Expected = @(200) },
    @{ Role = 'technical'; Path = '/audit/stats'; Expected = @(200) },
    @{ Role = 'technical'; Path = '/dashboard'; Expected = @(403) },
    @{ Role = 'technical'; Path = '/pets?limit=1'; Expected = @(403) }
)

$tokens = @{}
foreach ($role in $accounts.Keys) {
    $tokens[$role] = Get-Token $accounts[$role]
}

$failed = 0
foreach ($item in $matrix) {
    if (-not (Test-Endpoint -Role $item.Role -Token $tokens[$item.Role] -Path $item.Path -Expected $item.Expected)) {
        $failed += 1
    }
}

if ($failed -gt 0) {
    throw ("Matriz de permisos con {0} comprobaciones fallidas." -f $failed)
}
Write-Host ("Matriz de permisos superada: {0} comprobaciones." -f $matrix.Count) -ForegroundColor Green

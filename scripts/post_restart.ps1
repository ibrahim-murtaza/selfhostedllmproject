# Post-restart check and model warm-up for the Clarisync pilot box.
# Run on the box after RDP-ing in as AI (Docker Desktop and Ollama start at sign-in).
# Usage, from the repo root:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\post_restart.ps1
param([int]$WaitMinutes = 10)

$deadline = (Get-Date).AddMinutes($WaitMinutes)
$allOk = $true

function Wait-Ready($name, [scriptblock]$check) {
    while ((Get-Date) -lt $deadline) {
        try { if (& $check) { Write-Host ("[ok]   {0}" -f $name); return $true } } catch {}
        Start-Sleep -Seconds 5
    }
    Write-Host ("[FAIL] {0} not ready within {1} min" -f $name, $WaitMinutes)
    return $false
}

function Http-Ok($url) {
    (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200
}

# Windows services (NSSM): all four shared services plus Caddy
foreach ($svc in "clarisync-docling", "clarisync-gateway", "clarisync-ocr", "clarisync-gpulog", "clarisync-caddy") {
    $ok = Wait-Ready ("service " + $svc) ([scriptblock]::Create("(Get-Service '$svc').Status -eq 'Running'"))
    if (-not $ok) { $allOk = $false }
}

# Endpoints
$checks = @(
    @("Ollama (11434)",        "http://127.0.0.1:11434/api/tags"),
    @("Docling (8001)",        "http://127.0.0.1:8001/health"),
    @("Gateway (8000)",        "http://127.0.0.1:8000/health"),
    @("LibreChat prod (3080)", "http://127.0.0.1:3080/")
)
foreach ($c in $checks) {
    $url = $c[1]
    $ok = Wait-Ready $c[0] ([scriptblock]::Create("Http-Ok '$url'"))
    if (-not $ok) { $allOk = $false }
}

if (-not $allOk) { Write-Host "Skipping warm-up: something above is not ready."; exit 1 }

# Warm-up: loads the weights into Ollama and the OS file cache.
# Shows up in gateway_metrics.jsonl as a stream:false row (counted with title rows).
$body = '{"model":"quick-text","stream":false,"max_tokens":1,"messages":[{"role":"user","content":"hi"}]}'
$sw = [Diagnostics.Stopwatch]::StartNew()
try {
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/chat/completions" -ContentType "application/json" -Body $body -TimeoutSec 180 | Out-Null
    Write-Host ("[ok]   model warm in {0:N1} s" -f $sw.Elapsed.TotalSeconds)
} catch {
    Write-Host ("[FAIL] warm-up request failed: {0}" -f $_.Exception.Message)
    exit 1
}

try { & ollama ps } catch { Write-Host "(ollama ps not available in this shell)" }
Write-Host "Done."
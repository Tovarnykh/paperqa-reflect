param(
    [string]$ModelsPath = "$env:USERPROFILE\.ollama\models",
    [int]$Port = 11435
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $projectRoot '.cache\ollama'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$endpoint = "http://127.0.0.1:$Port"
try {
    $null = Invoke-RestMethod "$endpoint/api/version" -TimeoutSec 2
    Write-Output "Ollama already responds at $endpoint"
    exit 0
} catch { }
if (-not (Test-Path -LiteralPath $ModelsPath)) { throw "Model directory not found: $ModelsPath" }
$env:OLLAMA_HOST = "127.0.0.1:$Port"
$env:OLLAMA_MODELS = (Resolve-Path -LiteralPath $ModelsPath).Path
$env:OLLAMA_CONTEXT_LENGTH = '8192'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_FLASH_ATTENTION = '1'
$env:OLLAMA_KV_CACHE_TYPE = 'q8_0'
$env:OLLAMA_KEEP_ALIVE = '10m'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_NOPRUNE = '1'
$server = Start-Process -FilePath (Get-Command ollama).Source -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'stdout.log') -RedirectStandardError (Join-Path $logDir 'stderr.log')
$server.Id | Set-Content (Join-Path $logDir 'server.pid')
Write-Output "Started Ollama PID $($server.Id) at $endpoint; logs: $logDir"
$readyDeadline = (Get-Date).AddSeconds(180)
while ((Get-Date) -lt $readyDeadline) {
    if ($server.HasExited) { throw "Ollama exited; inspect $logDir\stderr.log" }
    try {
        $null = Invoke-RestMethod "$endpoint/api/version" -TimeoutSec 2
        Write-Output "Ollama is ready. Run: uv run --frozen pqa-reflect doctor"
        exit 0
    } catch { Start-Sleep -Seconds 2 }
}
throw "Ollama did not become ready within 180 seconds. Inspect $logDir\stderr.log"

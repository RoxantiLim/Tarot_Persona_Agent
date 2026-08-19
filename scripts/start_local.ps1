param(
    [int]$ApiPort = 8787,
    [int]$WebPort = 3000,
    [int]$HealthTimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LogsDir = Join-Path $ProjectRoot "logs"
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"
$Python = "E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv-clean\Scripts\python.exe"
$WebRoot = Join-Path $ProjectRoot "web"
$NodeModules = Join-Path $WebRoot "node_modules"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message"
}

function Wait-HttpOk([string]$Url, [int]$TimeoutSeconds) {
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        try {
            $Response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

if ($WebPort -ne 3000) {
    throw "scripts\start_web.ps1 currently starts Next.js on port 3000. Use -WebPort 3000."
}

if (-not (Test-Path $EnvFile)) {
    throw "Missing .env. Copy $EnvExample to $EnvFile and fill DEEPSEEK_API_KEY first."
}

if (-not (Test-Path $Python)) {
    throw "Python venv not found: $Python. Run scripts\setup_env.ps1 first."
}

if (-not (Test-Path $NodeModules)) {
    throw "web\node_modules not found. Run npm install in $WebRoot first."
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

Write-Step "Starting FastAPI on http://127.0.0.1:$ApiPort"
& (Join-Path $ProjectRoot "scripts\start_api.ps1") -Port $ApiPort

Write-Step "Starting Next.js on http://127.0.0.1:$WebPort"
& (Join-Path $ProjectRoot "scripts\start_web.ps1")

Write-Step "Checking local services"
$ApiReady = Wait-HttpOk "http://127.0.0.1:$ApiPort/api/health" $HealthTimeoutSeconds
$WebReady = Wait-HttpOk "http://127.0.0.1:$WebPort" $HealthTimeoutSeconds

Write-Host ""
Write-Host "Local startup summary"
Write-Host "  Frontend: http://127.0.0.1:$WebPort"
Write-Host "  Backend:  http://127.0.0.1:$ApiPort"
Write-Host "  API docs: http://127.0.0.1:$ApiPort/docs"
Write-Host "  Logs:     $LogsDir"
Write-Host ""
Write-Host "Readiness"
Write-Host "  FastAPI:  $(if ($ApiReady) { 'ready' } else { 'not ready yet - check logs\api.err.log' })"
Write-Host "  Next.js:  $(if ($WebReady) { 'ready' } else { 'not ready yet - check logs\web.err.log' })"

if (-not $ApiReady -or -not $WebReady) {
    exit 1
}

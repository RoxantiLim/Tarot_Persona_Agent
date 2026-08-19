$ErrorActionPreference = "SilentlyContinue"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PidFile = Join-Path $ProjectRoot "logs\cloudflared.pid"

if (-not (Test-Path $PidFile)) {
    Write-Host "No cloudflared pid file found at $PidFile."
    exit 0
}

$PidValue = (Get-Content -Raw $PidFile).Trim()
if (-not $PidValue) {
    Write-Host "cloudflared pid file is empty: $PidFile"
    exit 0
}

Stop-Process -Id ([int]$PidValue) -Force
Remove-Item $PidFile -Force
Write-Host "Stopped Cloudflare Tunnel process $PidValue."

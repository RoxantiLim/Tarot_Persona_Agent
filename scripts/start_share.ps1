param(
    [int]$ApiPort = 8787,
    [int]$WebPort = 3000,
    [int]$TunnelTimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LogsDir = Join-Path $ProjectRoot "logs"
$CloudflaredOutLog = Join-Path $LogsDir "cloudflared.out.log"
$CloudflaredErrLog = Join-Path $LogsDir "cloudflared.err.log"
$CloudflaredPidFile = Join-Path $LogsDir "cloudflared.pid"

function Read-TunnelUrl {
    param([string[]]$Paths)

    foreach ($Path in $Paths) {
        if (-not (Test-Path $Path)) {
            continue
        }
        $Text = Get-Content -Raw -ErrorAction SilentlyContinue $Path
        $Match = [regex]::Match($Text, "https://[-a-zA-Z0-9]+\.trycloudflare\.com")
        if ($Match.Success) {
            return $Match.Value
        }
    }
    return ""
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

Write-Host ""
Write-Host "==> Starting local app before opening a Cloudflare tunnel"
& (Join-Path $ProjectRoot "scripts\start_local.ps1") -ApiPort $ApiPort -WebPort $WebPort

$Cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $Cloudflared) {
    throw @"
cloudflared was not found on PATH.

Install Cloudflare Tunnel first:
  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

If you download a standalone helper, place it under E:\for-LLM\AUXI and add it to PATH.
"@
}

Remove-Item $CloudflaredOutLog, $CloudflaredErrLog -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==> Starting Cloudflare Quick Tunnel for http://127.0.0.1:$WebPort"
$TunnelArgs = @("tunnel", "--url", "http://127.0.0.1:$WebPort")
$Process = Start-Process `
    -FilePath $Cloudflared.Source `
    -ArgumentList $TunnelArgs `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $CloudflaredOutLog `
    -RedirectStandardError $CloudflaredErrLog `
    -PassThru

Set-Content -Path $CloudflaredPidFile -Value $Process.Id -Encoding ASCII

$TunnelUrl = ""
$Deadline = (Get-Date).AddSeconds($TunnelTimeoutSeconds)
while ((Get-Date) -lt $Deadline) {
    if ($Process.HasExited) {
        break
    }
    $TunnelUrl = Read-TunnelUrl @($CloudflaredOutLog, $CloudflaredErrLog)
    if ($TunnelUrl) {
        break
    }
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "Share startup summary"
Write-Host "  Local frontend: http://127.0.0.1:$WebPort"
Write-Host "  Local backend:  http://127.0.0.1:$ApiPort"
Write-Host "  API docs:       http://127.0.0.1:$ApiPort/docs"
Write-Host "  Tunnel PID:     $($Process.Id)"
Write-Host "  Logs:"
Write-Host "    $CloudflaredOutLog"
Write-Host "    $CloudflaredErrLog"

if ($TunnelUrl) {
    Write-Host ""
    Write-Host "Public share link:"
    Write-Host "  $TunnelUrl"
    Write-Host ""
    Write-Host "Only share this temporary link with trusted testers. Stop sharing with:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\stop_share.ps1"
} else {
    Write-Host ""
    Write-Host "Cloudflare tunnel did not print a trycloudflare.com URL in time."
    Write-Host "Check the cloudflared logs above. Common causes: cloudflared is outdated, a local config.yaml blocks Quick Tunnels, or the network is unavailable."
    exit 1
}

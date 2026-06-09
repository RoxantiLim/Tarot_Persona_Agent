$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WebRoot = Join-Path $ProjectRoot "web"
$LogsDir = Join-Path $ProjectRoot "logs"
$StdOutLog = Join-Path $LogsDir "web.out.log"
$StdErrLog = Join-Path $LogsDir "web.err.log"

if (-not (Test-Path (Join-Path $WebRoot "package.json"))) {
    throw "Next.js app not found: $WebRoot"
}

$ExistingPorts = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" -and $_.OwningProcess }

foreach ($Connection in $ExistingPorts) {
    Stop-Process -Id $Connection.OwningProcess -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

$PathValue = [System.Environment]::GetEnvironmentVariable("Path", "Process")
[System.Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[System.Environment]::SetEnvironmentVariable("Path", $PathValue, "Process")

$env:npm_config_cache = "E:\for-LLM\AUXI\npm-cache"
Remove-Item Env:\NEXT_PUBLIC_API_BASE_URL -ErrorAction SilentlyContinue
$Npm = "npm.cmd"
$Args = @("run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3000")

$Process = Start-Process `
    -FilePath $Npm `
    -ArgumentList $Args `
    -WorkingDirectory $WebRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $StdOutLog `
    -RedirectStandardError $StdErrLog `
    -PassThru
Start-Sleep -Seconds 5

Write-Host "Next.js frontend should be available at:"
Write-Host "  http://127.0.0.1:3000"
Write-Host "Process id:"
Write-Host "  $($Process.Id)"
Write-Host "Logs:"
Write-Host "  $StdOutLog"
Write-Host "  $StdErrLog"

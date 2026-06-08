param(
    [int]$Port = 8787
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv-clean\Scripts\python.exe"
$LogsDir = Join-Path $ProjectRoot "logs"
$StdOutLog = Join-Path $LogsDir "api.out.log"
$StdErrLog = Join-Path $LogsDir "api.err.log"

if (-not (Test-Path $Python)) {
    throw "Python venv not found: $Python. Run scripts\setup_env.ps1 first."
}

$ExistingPorts = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" -and $_.OwningProcess }

foreach ($Connection in $ExistingPorts) {
    Stop-Process -Id $Connection.OwningProcess -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

$PathValue = [System.Environment]::GetEnvironmentVariable("Path", "Process")
[System.Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[System.Environment]::SetEnvironmentVariable("Path", $PathValue, "Process")

$Args = @(
    "-m", "uvicorn", "api.main:app",
    "--host", "127.0.0.1",
    "--port", "$Port"
)

$Process = Start-Process `
    -FilePath $Python `
    -ArgumentList $Args `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $StdOutLog `
    -RedirectStandardError $StdErrLog `
    -PassThru
Start-Sleep -Seconds 3

Write-Host "FastAPI should be available at:"
Write-Host "  http://127.0.0.1:$Port"
Write-Host "Docs:"
Write-Host "  http://127.0.0.1:$Port/docs"
Write-Host "Process id:"
Write-Host "  $($Process.Id)"
Write-Host "Logs:"
Write-Host "  $StdOutLog"
Write-Host "  $StdErrLog"

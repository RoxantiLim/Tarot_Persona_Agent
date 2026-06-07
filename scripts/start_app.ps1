$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv-clean\Scripts\python.exe"
$LogsDir = Join-Path $ProjectRoot "logs"
$StdOutLog = Join-Path $LogsDir "streamlit.out.log"
$StdErrLog = Join-Path $LogsDir "streamlit.err.log"

if (-not (Test-Path $Python)) {
    throw "Python venv not found: $Python. Run scripts\setup_env.ps1 first."
}

$ExistingPorts = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" -and $_.OwningProcess }

foreach ($Port in $ExistingPorts) {
    Stop-Process -Id $Port.OwningProcess -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

# The Codex shell can expose both Path and PATH on Windows. Start-Process
# treats them as duplicate environment keys, so normalize the inherited value.
$PathValue = [System.Environment]::GetEnvironmentVariable("Path", "Process")
[System.Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[System.Environment]::SetEnvironmentVariable("Path", $PathValue, "Process")

$Args = @(
    "-m", "streamlit", "run", "app.py",
    "--server.headless", "true",
    "--server.address", "127.0.0.1",
    "--server.port", "8501",
    "--browser.gatherUsageStats", "false"
)

$Process = Start-Process `
    -FilePath $Python `
    -ArgumentList $Args `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $StdOutLog `
    -RedirectStandardError $StdErrLog `
    -PassThru
Start-Sleep -Seconds 5

Write-Host "Streamlit should be available at:"
Write-Host "  http://127.0.0.1:8501"
Write-Host "Process id:"
Write-Host "  $($Process.Id)"
Write-Host "Logs:"
Write-Host "  $StdOutLog"
Write-Host "  $StdErrLog"

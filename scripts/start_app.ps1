$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Python venv not found: $Python. Run scripts\setup_env.ps1 first."
}

$Existing = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*streamlit*" -and $_.CommandLine -like "*Tarot_Persona_Agent*" }

foreach ($Process in $Existing) {
    Stop-Process -Id $Process.ProcessId -Force
}

$Args = @(
    "-m", "streamlit", "run", "app.py",
    "--server.headless", "true",
    "--server.address", "127.0.0.1",
    "--server.port", "8501",
    "--browser.gatherUsageStats", "false"
)

Start-Process -FilePath $Python -ArgumentList $Args -WorkingDirectory $ProjectRoot -WindowStyle Hidden
Start-Sleep -Seconds 5

Write-Host "Streamlit should be available at:"
Write-Host "  http://127.0.0.1:8501"

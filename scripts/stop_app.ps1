$ErrorActionPreference = "SilentlyContinue"

$ProjectNeedle = "Tarot_Persona_Agent"
$Processes = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*streamlit*" -and $_.CommandLine -like "*$ProjectNeedle*" }

foreach ($Process in $Processes) {
    Stop-Process -Id $Process.ProcessId -Force
}

Write-Host "Stopped $($Processes.Count) Streamlit process(es) for $ProjectNeedle."

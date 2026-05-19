param(
    [string]$AuxRoot = "E:\for-LLM\AUXI\Tarot_Persona_Agent"
)

$ErrorActionPreference = "Stop"

$VenvPath = Join-Path $AuxRoot ".venv"
$ModelPath = Join-Path $AuxRoot "models"
$PipCache = Join-Path $AuxRoot "pip-cache"

New-Item -ItemType Directory -Force -Path $AuxRoot | Out-Null
New-Item -ItemType Directory -Force -Path $ModelPath | Out-Null
New-Item -ItemType Directory -Force -Path $PipCache | Out-Null

if (-not (Test-Path $VenvPath)) {
    python -m venv $VenvPath
}

$Python = Join-Path $VenvPath "Scripts\python.exe"

& $Python -m pip install --upgrade pip
& $Python -m pip install --cache-dir $PipCache --force-reinstall torch==2.6.0+cu124 --index-url https://download.pytorch.org/whl/cu124
& $Python -m pip install --cache-dir $PipCache -r requirements.txt

Write-Host ""
Write-Host "Environment ready:"
Write-Host "  $VenvPath"
Write-Host ""
Write-Host "Run:"
Write-Host "  $Python scripts\ingest_documents.py"
Write-Host "  $Python -m streamlit run app.py"

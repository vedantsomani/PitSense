$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
try {
    $taskHealth = Invoke-WebRequest 'http://127.0.0.1:8501/_stcore/health' -UseBasicParsing -TimeoutSec 2
    if ($taskHealth.StatusCode -eq 200) {
        Start-Process 'http://127.0.0.1:8501'
        exit 0
    }
} catch { }
if (-not (Test-Path '.venv/Scripts/python.exe')) { & ./setup.ps1 }
& ./.venv/Scripts/python.exe -m streamlit run app.py

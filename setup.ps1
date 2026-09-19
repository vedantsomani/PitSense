$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12, then run setup.ps1 again.' }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& ./.venv/Scripts/python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
& ./.venv/Scripts/python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
Write-Host 'Ready. Double-click Start Dashboard.cmd or run .\run.ps1'

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (Test-Path 'reports/dashboard.pid') {
    $taskServerId = [int](Get-Content 'reports/dashboard.pid')
    $taskProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$taskServerId"
    $taskExpectedPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if ($taskProcess -and $taskProcess.ExecutablePath -eq $taskExpectedPython -and $taskProcess.CommandLine -match 'streamlit') {
        Stop-Process -Id $taskServerId
        Write-Host 'Dashboard stopped.'
    } else {
        Write-Host 'The saved dashboard process is no longer running.'
    }
} else {
    Write-Host 'For a dashboard started in a terminal, press Ctrl+C in that terminal.'
}

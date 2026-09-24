$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$novaPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $novaPython)) {
    Write-Error 'Set up the Python environment first. See README.md.'
    exit 1
}
Write-Host 'novaFinance: http://127.0.0.1:8000 (Ctrl+C to stop)'
& $novaPython -m uvicorn main.main:app --host 127.0.0.1 --port 8000

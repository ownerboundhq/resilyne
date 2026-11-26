$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Python virtual environment not found. See finance/README.md." }
& $python -m finance.desktop
if ($LASTEXITCODE -ne 0) { throw "Desktop launcher exited with code $LASTEXITCODE" }

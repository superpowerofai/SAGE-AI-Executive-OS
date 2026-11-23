$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$database = Join-Path $root "runtime\data\sage.db"

if (-not (Test-Path $python)) { throw "SAGE virtual environment is missing: $python" }
if (-not (Test-Path (Split-Path -Parent $database))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $database) | Out-Null
}

$arguments = '-m sage --db "' + $database + '" serve --host 127.0.0.1 --port 8765'
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -PassThru -WindowStyle Normal
Write-Host "Started SAGE server process $($process.Id)."

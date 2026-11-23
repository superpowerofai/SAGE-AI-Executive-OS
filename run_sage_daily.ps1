$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$database = Join-Path $root "runtime\data\sage.db"
$logDirectory = Join-Path $root "runtime\logs"
$logFile = Join-Path $logDirectory "daily-generation.log"

if (-not (Test-Path $python)) { throw "SAGE virtual environment is missing: $python" }
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$lines = @("[$stamp] SAGE daily generation started")

foreach ($command in @("generate-recurring", "generate-recurring-obligations")) {
    $output = & $python -m sage --db $database $command 2>&1
    $exitCode = $LASTEXITCODE
    $lines += "COMMAND: $command"
    $lines += ($output | ForEach-Object { "$_" })
    if ($exitCode -ne 0) {
        $lines += "FAILED with exit code $exitCode"
        Add-Content -Path $logFile -Value $lines -Encoding UTF8
        exit $exitCode
    }
}

$lines += "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] SAGE daily generation completed"
Add-Content -Path $logFile -Value $lines -Encoding UTF8

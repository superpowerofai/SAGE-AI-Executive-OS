@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo SAGE is not installed yet.
    echo Run the installation steps in README.md first.
    pause
    exit /b 1
)

if not exist "runtime\data" mkdir "runtime\data"

if not defined SAGE_AI_BASE_URL set "SAGE_AI_BASE_URL=http://127.0.0.1:11434/v1"
if not defined SAGE_AI_MODEL set "SAGE_AI_MODEL=qwen3:1.7b"

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo Starting SAGE local executive cockpit...
    echo Local AI endpoint: %SAGE_AI_BASE_URL%
    echo AI model: %SAGE_AI_MODEL%
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_sage_server.ps1"
    if errorlevel 1 (
        echo Failed to start SAGE server.
        pause
        exit /b 1
    )
    timeout /t 3 /nobreak >nul
)

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo SAGE did not start. Check Python installation and port 8765.
    pause
    exit /b 1
)

start "" "http://127.0.0.1:8765"
echo SAGE is running at http://127.0.0.1:8765
echo Close the SAGE Server window to stop the server.
pause
endlocal

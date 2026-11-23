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

echo Starting SAGE local executive cockpit...
echo Open http://127.0.0.1:8765 in your browser.
echo Keep this window open while using SAGE. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m sage --db "runtime\data\sage.db" serve --host 127.0.0.1 --port 8765
endlocal

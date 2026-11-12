# Starts the whole SafeWatch stack in three windows: backend (FastAPI), detector (YOLO), frontend (React).
# Run from PowerShell:   powershell -ExecutionPolicy Bypass -File .\start-safewatch.ps1   (or double-click start-safewatch.bat)
# PostgreSQL must already be running (it starts automatically as a Windows service).
# Each part is only started if it is not already running, so running this twice never creates duplicates.

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-Port($port) {
    [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

$svc = Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Where-Object Status -eq 'Running'
if (-not $svc) { Write-Warning "No running PostgreSQL service found - start it from Services first." }

if (Test-Port 8000) {
    Write-Host "Backend already running (port 8000) - not starting another." -ForegroundColor Yellow
} else {
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "`$host.UI.RawUI.WindowTitle='SafeWatch backend'; cd '$root\backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"
    Start-Sleep -Seconds 4
}

if (Test-Port 8100) {
    Write-Host "Detector already running (port 8100) - not starting another." -ForegroundColor Yellow
} else {
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "`$host.UI.RawUI.WindowTitle='SafeWatch detector'; cd '$root\detector'; .\.venv\Scripts\python.exe main.py"
}

if (Test-Port 5173) {
    Write-Host "Website already running (port 5173) - not starting another." -ForegroundColor Yellow
} else {
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "`$host.UI.RawUI.WindowTitle='SafeWatch frontend'; cd '$root\frontend'; npm run dev -- --strictPort"
    Start-Sleep -Seconds 6
}

Start-Process 'http://localhost:5173'
Write-Host "SafeWatch: dashboard http://localhost:5173  |  API docs http://127.0.0.1:8000/docs"

@echo off
title POR Signboard Auto Launcher
set PORT=5000

echo [1/2] Starting Docker Containers...
docker-compose up -d

echo Waiting for the web service to be ready on port %PORT%...
:check_ready
curl -s --max-time 1 http://127.0.0.1:%PORT%/show >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto check_ready
)

echo [2/2] Launching Chrome in Kiosk Mode...
echo If Chrome does not open, please make sure it is installed.
start chrome --kiosk "http://127.0.0.1:%PORT%/show" --user-data-dir="%TEMP%\POR_Chrome_Profile" --no-first-run --force-device-scale-factor=1.0

echo.
echo ==========================================
echo   Signboard System is now RUNNING.
echo   TV Display: http://localhost:%PORT%/show
echo   Admin Page: http://localhost:%PORT%/manage
echo ==========================================
echo.
pause

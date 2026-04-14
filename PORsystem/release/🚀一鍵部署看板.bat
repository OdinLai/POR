@echo off
setlocal
title POR Signboard - One-Click Deployment
set PORT=5000
set IMAGE_FILE=POR_Signboard_v1.tar

echo ==========================================
echo   POR Signboard Offline Deployer
echo ==========================================
echo.

:: 1. 偵測 IP
echo [1/3] Detecting Host LAN IP...
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Get-NetIPInterface | Where-Object ConnectionState -eq 'Connected' | Get-NetIPAddress -AddressFamily IPv4 | Select-Object -First 1).IPAddress"`) do set HOST_IP=%%i

if "%HOST_IP%"=="" (
    set HOST_IP=127.0.0.1
)
echo Detected Host IP: %HOST_IP%

:: 2. 載入映像檔 (如果尚未載入)
echo.
echo [2/3] Checking Docker Image...
docker image inspect signboard_app:latest >nul 2>&1
if errorlevel 1 (
    if exist %IMAGE_FILE% (
        echo Loading image from %IMAGE_FILE%...
        docker load -i %IMAGE_FILE%
    ) else (
        echo [ERROR] %IMAGE_FILE% not found!
        pause
        exit /b
    )
) else (
    echo Image already exists, skipping load.
)

:: 3. 啟動容器
echo.
echo [3/3] Starting System...
call docker-compose down >nul 2>&1
call docker-compose up -d
if errorlevel 1 (
    echo [ERROR] Startup failed.
    pause
    exit /b
)

echo.
echo Waiting for service...
:check_ready
curl -s --max-time 1 http://127.0.0.1:%PORT%/show >nul 2>&1
if errorlevel 1 (
    <nul set /p=.
    timeout /t 2 /nobreak >nul
    goto check_ready
)

echo.
echo Launching Browser...
start chrome --kiosk "http://127.0.0.1:%PORT%/show" --user-data-dir="%TEMP%\POR_Chrome_Profile" --no-first-run --force-device-scale-factor=1.0
if errorlevel 1 (
    start http://127.0.0.1:%PORT%/show
)

echo.
echo ==========================================
echo   DEPLOYMENT SUCCESSFUL!
echo ==========================================
pause

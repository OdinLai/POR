@echo off
title POR Signboard Auto Launcher
set PORT=5000

echo [1/2] Detecting Host LAN IP...
:: 使用更精準的路徑追蹤來找到連網網卡的 IP
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Get-NetIPInterface | Where-Object ConnectionState -eq 'Connected' | Get-NetIPAddress -AddressFamily IPv4 | Select-Object -First 1).IPAddress"`) do set HOST_IP=%%i

if "%HOST_IP%"=="" (
    echo [WARNING] Could not detect LAN IP automatisch. 
    echo Please check your network connection.
    set HOST_IP=127.0.0.1
)
echo Detected Host IP: %HOST_IP%

echo [1/2] Starting Docker Containers...
:: 確保每次啟動都是全新的環境變數
call docker-compose down >nul 2>&1
call docker-compose up -d --build
if errorlevel 1 (
    echo [ERROR] Docker startup failed.
    pause
    exit /b
)

echo.
echo Waiting for the web service to be ready on port %PORT%...
echo This may take a few seconds...

:check_ready
:: 使用 curl 測試，並增加嘗試次數限制
set /a retry_count+=1
if %retry_count% GTR 30 (
    echo [WARNING] Web service timeout. Attempting to launch browser anyway...
    goto launch_chrome
)
curl -s --max-time 1 http://127.0.0.1:%PORT%/show >nul 2>&1
if errorlevel 1 (
    <nul set /p=.
    timeout /t 2 /nobreak >nul
    goto check_ready
)

:launch_chrome
echo.
echo [2/2] Launching Browser...
:: 嘗試啟動 Chrome，若失敗則回退到系統預設瀏覽器
start chrome --kiosk "http://127.0.0.1:%PORT%/show" --user-data-dir="%TEMP%\POR_Chrome_Profile" --no-first-run --force-device-scale-factor=1.0
if errorlevel 1 (
    echo Chrome not found, using default browser...
    start http://127.0.0.1:%PORT%/show
)

echo.
echo ==========================================
echo   Signboard System is now RUNNING.
echo   TV Display: http://localhost:%PORT%/show
echo   Admin Page: http://localhost:%PORT%/manage
echo ==========================================
echo.
pause

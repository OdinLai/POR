@echo off
title POR Signboard - Create Release Package
set SERVICE_NAME=signboard-app
set IMAGE_NAME=signboard_app
set TAG=latest
set OUTPUT_FILE=release\POR_Signboard_v1.tar

echo ==========================================
echo   POR Signboard Release Builder
echo ==========================================
echo.

echo [1/3] Building latest Docker image...
call docker-compose build %SERVICE_NAME%
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b
)

echo.
echo [2/3] Exporting image to .tar file...
echo This may take a minute, please wait...
call docker save -o %OUTPUT_FILE% %IMAGE_NAME%:%TAG%
if errorlevel 1 (
    echo [ERROR] Export failed.
    pause
    exit /b
)

echo.
echo [3/3] Finalizing deployment scripts...
:: 移除舊的高風險腳本（若存在）
if exist "release\🚀一鍵部署看板.bat" del /q "release\🚀一鍵部署看板.bat"

:: 建立高相容性的 deploy.bat
(
echo @echo off
echo setlocal
echo title POR_Signboard_Deploy
echo.
echo :: 1. Setup database folder
echo if not exist database mkdir database
echo.
echo :: 2. Detect IP
echo echo Detecting LAN IP...
echo powershell -NoProfile -Command "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Get-NetIPInterface | Where-Object ConnectionState -eq 'Connected' | Get-NetIPAddress -AddressFamily IPv4 | Select-Object -First 1).IPAddress" > ip.txt
echo set /p HOST_IP=^<ip.txt
echo del ip.txt
echo if "%%HOST_IP%%"=="" set HOST_IP=127.0.0.1
echo echo Detected IP: %%HOST_IP%%
echo.
echo :: 3. Load Image (if needed)
echo if exist %OUTPUT_FILE% (
echo     docker image inspect %IMAGE_NAME%:%TAG% ^>nul 2^>^&1
echo     if errorlevel 1 (
echo         echo Loading Image...
echo         docker load -i %OUTPUT_FILE%
echo     )
echo )
echo.
echo :: 4. Start System
echo echo Starting Docker Services...
echo docker-compose down ^>nul 2^>^&1
echo docker-compose up -d
echo if errorlevel 1 (
echo     echo [ERROR] Docker failed to start.
echo     docker-compose logs
echo     pause 
echo     exit /b
echo )
echo.
echo :: 5. Launch Browser (Kiosk mode priority)
echo echo Launching Signboard in 5 seconds...
echo timeout /t 5
echo start chrome --kiosk "http://127.0.0.1:5000/show" --user-data-dir="%%TEMP%%\POR_Chrome" --no-first-run
echo if errorlevel 1 (
echo     start http://127.0.0.1:5000/show
echo )
echo.
echo === DEPLOYMENT SUCCESSFUL ===
echo pause
) > release\deploy.bat

echo Done.

echo.
echo ==========================================
echo   SUCCESS! Release package is ready.
echo   Location: d:\PythonWorking\POR\PORsystem\release\
echo ==========================================
echo.
pause

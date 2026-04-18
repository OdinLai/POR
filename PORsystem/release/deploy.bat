@echo off
setlocal
title POR_Signboard_Deploy

:: 1. Setup instance folder
if not exist instance mkdir instance

:: 2. Get IP
echo Checking IP...
powershell -Command "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Get-NetIPInterface | Where-Object ConnectionState -eq 'Connected' | Get-NetIPAddress -AddressFamily IPv4 | Select-Object -First 1).IPAddress" > ip.txt
set /p HOST_IP=<ip.txt
del ip.txt
if "%HOST_IP%"=="" set HOST_IP=127.0.0.1
echo IP: %HOST_IP%

:: 3. Load Image
if exist POR_Signboard_v1.tar (
    echo Loading Image...
    docker load -i POR_Signboard_v1.tar
)

:: 4. Start
echo Starting Docker...
docker-compose down
docker-compose up -d

echo.
echo Launching Signboard...
timeout /t 5
start http://127.0.0.1:5000/show

pause

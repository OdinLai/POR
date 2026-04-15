@echo off
title POR Signboard - Create Release Package
set IMAGE_NAME=signboard-app
set TAG=latest
set OUTPUT_FILE=release\POR_Signboard_v1.tar

echo ==========================================
echo   POR Signboard Release Builder
echo ==========================================
echo.

echo [1/3] Building latest Docker image...
call docker-compose build %IMAGE_NAME%
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
echo [3/3] Preparing deployment files...
copy /y config.inf release\config.inf >nul
echo Done.

echo.
echo ==========================================
echo   SUCCESS! Release package is ready.
echo   Location: d:\PythonWorking\POR\PORsystem\release\
echo ==========================================
echo.
pause

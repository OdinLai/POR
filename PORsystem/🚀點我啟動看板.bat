@echo off
echo [INFO] Starting Projection Signboard System...
docker-compose up --build -d
echo [SUCCESS] System is up!
echo Accessing at http://localhost:5000
pause

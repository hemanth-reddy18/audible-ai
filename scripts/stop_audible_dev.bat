@echo off
echo Stopping Audible services on ports 8000 and 3010...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Stopping API process PID %%a...
    taskkill /PID %%a /F /T >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3010 ^| findstr LISTENING') do (
    echo Stopping Web process PID %%a...
    taskkill /PID %%a /F /T >nul 2>&1
)

echo All Audible services stopped.

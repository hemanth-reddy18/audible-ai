@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo           AUDIBLE AI - REAL-TIME VOICE AGENT PLATFORM
echo                  Local Windows 11 Environment
echo ================================================================

set "BASE_DIR=%~dp0.."
cd /d "%BASE_DIR%"

if not exist "%BASE_DIR%\run" mkdir "%BASE_DIR%\run"
if not exist "%BASE_DIR%\logs" mkdir "%BASE_DIR%\logs"

echo Checking environment files...
if not exist "apps\api\.env" (
    echo Creating apps\api\.env...
    copy "apps\api\.env.example" "apps\api\.env"
)

if not exist "apps\web\.env" (
    echo Creating apps\web\.env...
    (
        echo BACKEND_URL=http://localhost:8000
        echo NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
        echo UI_PORT=3010
        echo NEXT_PUBLIC_APP_URL=http://localhost:3010
        echo NEXT_PUBLIC_NODE_ENV=development
    ) > "apps\web\.env"
)

echo Starting Audible Core API on port 8000...
start "Audible API" /B cmd /c "%~dp0run_api.bat > logs\audible_api.log 2>&1"

echo Starting Audible Web Frontend on port 3010...
start "Audible Web" /B cmd /c "%~dp0run_web.bat > logs\audible_web.log 2>&1"

echo ================================================================
echo                 AUDIBLE SERVICES LAUNCHED
echo ================================================================
echo   Frontend:     http://localhost:3010
echo   Backend API:  http://localhost:8000
echo   API Docs:     http://localhost:8000/docs
echo   Logs:         type logs\audible_api.log
echo                 type logs\audible_web.log
echo   Stop Script:  scripts\stop_audible_dev.bat
echo ================================================================

@echo off
set "BASE_DIR=%~dp0.."
cd /d "%BASE_DIR%"
set "PYTHONPATH=%BASE_DIR%\apps;%BASE_DIR%\apps\api;%PYTHONPATH%"
python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload

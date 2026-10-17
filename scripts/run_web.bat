@echo off
set "BASE_DIR=%~dp0.."
cd /d "%BASE_DIR%\apps\web"
set "UI_PORT=3010"
call npm.cmd run dev

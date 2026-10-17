# Audible AI Dev Launcher for Windows 11 PowerShell
param (
    [int]$UiPort = 3010,
    [int]$ApiPort = 8000
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseDir   = Split-Path -Parent $ScriptDir
Set-Location $BaseDir

$RunDir  = Join-Path $BaseDir 'run'
$LogsDir = Join-Path $BaseDir 'logs'
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "          AUDIBLE AI - REAL-TIME VOICE AGENT PLATFORM           " -ForegroundColor Cyan
Write-Host "                 Local Windows 11 Environment                   " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Frontend:  http://localhost:$UiPort" -ForegroundColor Green
Write-Host "  Backend:   http://localhost:$ApiPort" -ForegroundColor Green
Write-Host "  API Docs:  http://localhost:$ApiPort/docs" -ForegroundColor Green

# 1. Environment files
$ApiEnv = Join-Path $BaseDir 'apps\api\.env'
$WebEnv = Join-Path $BaseDir 'apps\web\.env'

if (-not (Test-Path $ApiEnv)) {
    Write-Host "Creating $ApiEnv..." -ForegroundColor Yellow
    Copy-Item (Join-Path $BaseDir 'apps\api\.env.example') $ApiEnv
}

if (-not (Test-Path $WebEnv)) {
    Write-Host "Creating $WebEnv..." -ForegroundColor Yellow
    $webEnvContent = @"
BACKEND_URL=http://localhost:$ApiPort
NEXT_PUBLIC_BACKEND_URL=http://localhost:$ApiPort
UI_PORT=$UiPort
NEXT_PUBLIC_APP_URL=http://localhost:$UiPort
NEXT_PUBLIC_NODE_ENV=development
"@
    Set-Content -Path $WebEnv -Value $webEnvContent -Encoding UTF8
}

# 2. Stop stale listeners on ports
foreach ($port in @($ApiPort, $UiPort)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        foreach ($conn in $conns) {
            Write-Host "Stopping stale listener on port $port (PID $($conn.OwningProcess))..." -ForegroundColor DarkGray
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

# 3. Launch Audible API
$ApiLog = Join-Path $LogsDir 'audible_api.log'
$apiBat = Join-Path $ScriptDir 'run_api.bat'
$apiProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$apiBat`" > `"$ApiLog`" 2>&1" -PassThru -WindowStyle Hidden
Set-Content -Path (Join-Path $RunDir 'audible_api.pid') -Value $apiProcess.Id
Write-Host "Audible API started [PID: $($apiProcess.Id)]" -ForegroundColor Green

# 4. Launch Audible Web
$WebLog = Join-Path $LogsDir 'audible_web.log'
$webBat = Join-Path $ScriptDir 'run_web.bat'
$webProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$webBat`" > `"$WebLog`" 2>&1" -PassThru -WindowStyle Hidden
Set-Content -Path (Join-Path $RunDir 'audible_web.pid') -Value $webProcess.Id
Write-Host "Audible Web started [PID: $($webProcess.Id)]" -ForegroundColor Green

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Services launched. Monitor logs via: Get-Content logs\audible_web.log -Tail 20" -ForegroundColor Gray
Write-Host "  To stop all services: .\scripts\stop_audible_dev.ps1" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Cyan

# Audible AI Dev Launcher for Windows 11 PowerShell
param (
    [int]$GatewayPort = 3010,
    [int]$NextJsPort  = 3011,
    [int]$ApiPort     = 8000,
    [switch]$NoBrowser
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
Write-Host "                 Single-Origin Localhost Architecture           " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Unified App & Gateway: http://localhost:$GatewayPort" -ForegroundColor Green
Write-Host "  API Documentation:     http://localhost:$GatewayPort/docs" -ForegroundColor Green
Write-Host "  Internal FastAPI:      http://127.0.0.1:$ApiPort" -ForegroundColor DarkGray
Write-Host "  Internal Next.js SSR:  http://127.0.0.1:$NextJsPort" -ForegroundColor DarkGray
Write-Host ""

# 1. Check Ollama Local AI Inference
Write-Host "[1/5] Checking Ollama daemon (127.0.0.1:11434)..." -ForegroundColor Yellow
$ollamaRunning = $false
try {
    $ollamaVer = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -TimeoutSec 2 -ErrorAction Stop
    $ollamaRunning = $true
    Write-Host "  Ollama is active (Version: $($ollamaVer.version))." -ForegroundColor Green
} catch {
    Write-Host "  Ollama not responding. Attempting to start local Ollama daemon..." -ForegroundColor Yellow
    $ollamaPath = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path $ollamaPath) {
        Start-Process -FilePath $ollamaPath -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        try {
            $ollamaVer = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -TimeoutSec 2 -ErrorAction Stop
            $ollamaRunning = $true
            Write-Host "  Ollama started successfully." -ForegroundColor Green
        } catch {
            Write-Host "  Warning: Ollama did not start immediately. Continuing..." -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "  Notice: Ollama not found at default location. Ensure Ollama is running for local AI inference." -ForegroundColor DarkYellow
    }
}

# 2. Verify environment configuration
Write-Host "[2/5] Verifying environment configurations..." -ForegroundColor Yellow
$ApiEnv = Join-Path $BaseDir 'apps\api\.env'
$WebEnv = Join-Path $BaseDir 'apps\web\.env'

if (-not (Test-Path $ApiEnv)) {
    Write-Host "  Creating $ApiEnv..." -ForegroundColor Yellow
    Copy-Item (Join-Path $BaseDir 'apps\api\.env.example') $ApiEnv
}

if (-not (Test-Path $WebEnv)) {
    Write-Host "  Creating $WebEnv..." -ForegroundColor Yellow
    $webEnvContent = @"
BACKEND_URL=http://localhost:$GatewayPort
NEXT_PUBLIC_BACKEND_URL=http://localhost:$GatewayPort
UI_PORT=$GatewayPort
NEXT_PUBLIC_APP_URL=http://localhost:$GatewayPort
NEXT_PUBLIC_NODE_ENV=development
"@
    Set-Content -Path $WebEnv -Value $webEnvContent -Encoding UTF8
}

# 3. Clean up stale listeners specifically on Audible ports
Write-Host "[3/5] Cleaning up stale listeners on ports $GatewayPort, $NextJsPort, $ApiPort..." -ForegroundColor Yellow
foreach ($port in @($GatewayPort, $NextJsPort, $ApiPort)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        foreach ($conn in $conns) {
            Write-Host "  Stopping stale process on port $port (PID $($conn.OwningProcess))..." -ForegroundColor DarkGray
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}
Start-Sleep -Seconds 1

# 4. Launch Audible API & Web Gateway
Write-Host "[4/5] Starting Audible services..." -ForegroundColor Yellow

# 4a. Audible API
$ApiLog = Join-Path $LogsDir 'audible_api.log'
$apiBat = Join-Path $ScriptDir 'run_api.bat'
$apiProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$apiBat`" > `"$ApiLog`" 2>&1" -PassThru -WindowStyle Hidden
Set-Content -Path (Join-Path $RunDir 'audible_api.pid') -Value $apiProcess.Id
Write-Host "  Audible API started [PID: $($apiProcess.Id)]" -ForegroundColor Green

# 4b. Audible Web + Gateway
$WebLog = Join-Path $LogsDir 'audible_web.log'
$webBat = Join-Path $ScriptDir 'run_web.bat'
$webProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$webBat`" > `"$WebLog`" 2>&1" -PassThru -WindowStyle Hidden
Set-Content -Path (Join-Path $RunDir 'audible_web.pid') -Value $webProcess.Id
Write-Host "  Audible Web & Gateway started [PID: $($webProcess.Id)]" -ForegroundColor Green

# 5. Health Check & Ready Notification
Write-Host "[5/5] Waiting for unified gateway readiness on http://localhost:$GatewayPort..." -ForegroundColor Yellow
$healthUrl = "http://localhost:$GatewayPort/api/config/version"
$maxAttempts = 40
$attempt = 0
$ready = $false

while ($attempt -lt $maxAttempts) {
    $attempt++
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3 -ErrorAction Stop
        if ($resp -and $resp.backend -and $resp.backend.status -eq 'reachable') {
            $ready = $true
            break
        }
    } catch {
        # Waiting for compilation or startup
    }
    Write-Host -NoNewline "."
}
Write-Host ""

if ($ready) {
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host "  AUDIBLE AI IS READY AND OPERATIONAL!                          " -ForegroundColor Green
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host "  Open: http://localhost:$GatewayPort" -ForegroundColor Cyan
    Write-Host "  Docs: http://localhost:$GatewayPort/docs" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  To stop: .\scripts\stop_audible_dev.ps1" -ForegroundColor Yellow
    Write-Host "================================================================" -ForegroundColor Green

    if (-not $NoBrowser) {
        Write-Host "Opening Audible AI in your browser..." -ForegroundColor Green
        Start-Process "http://localhost:$GatewayPort"
    }
} else {
    Write-Host "================================================================" -ForegroundColor DarkYellow
    Write-Host "  Services launched. App is still initializing in the background." -ForegroundColor DarkYellow
    Write-Host "  Check logs: Get-Content logs\audible_web.log -Tail 20" -ForegroundColor Gray
    Write-Host "  Once ready, open: http://localhost:$GatewayPort" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor DarkYellow
}

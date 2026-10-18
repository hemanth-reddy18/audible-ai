# Audible AI Dev Stopper for Windows 11 PowerShell
param (
    [int]$GatewayPort = 3010,
    [int]$NextJsPort  = 3011,
    [int]$ApiPort     = 8000
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseDir   = Split-Path -Parent $ScriptDir
$RunDir    = Join-Path $BaseDir 'run'

Write-Host "Stopping Audible AI services..." -ForegroundColor Yellow

# 1. Kill via stored PID files
foreach ($name in @('audible_api.pid', 'audible_web.pid')) {
    $pidFile = Join-Path $RunDir $name
    if (Test-Path $pidFile) {
        $procId = (Get-Content $pidFile -Raw).Trim()
        if ($procId) {
            Write-Host "  Stopping recorded process PID $procId ($name)..." -ForegroundColor DarkGray
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

# 2. Terminate any remaining listeners on Audible's specific ports
foreach ($port in @($GatewayPort, $NextJsPort, $ApiPort)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        foreach ($conn in $conns) {
            Write-Host "  Stopping process PID $($conn.OwningProcess) listening on port $port..." -ForegroundColor DarkGray
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "Audible AI services stopped cleanly." -ForegroundColor Green

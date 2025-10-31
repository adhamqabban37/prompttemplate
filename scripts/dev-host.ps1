<#
XenlixAI host-native dev launcher

What it does
- Starts Docker services: db, redis, adminer
- Starts FastAPI backend on host with: uvicorn app.main:app --reload --port 8001
- Starts RQ worker on host (default queue)
- Starts Vite frontend (port 5174)

Assumptions
- Python venv exists at backend\.venv
- Node/NPM available on PATH
- Docker Desktop running (Compose v2)
Usage
  pwsh -NoLogo -NoProfile -File .\scripts\dev-host.ps1
#>

$ErrorActionPreference = 'Stop'

# Resolve paths (handles spaces)
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot    = (Resolve-Path (Join-Path $ScriptDir '..')).Path
$BackendDir  = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$PythonExe   = Join-Path $BackendDir '.venv\Scripts\python.exe'

Write-Host "=== XenlixAI: host-native dev ===" -ForegroundColor Cyan
Write-Host "Repo Root: $RepoRoot" -ForegroundColor DarkCyan

# 1) Start infra via Docker (db, redis, adminer)
Write-Host "[1/4] Starting containers (db, redis, adminer)..." -ForegroundColor Yellow
Push-Location $RepoRoot
try {
  docker compose up -d db redis adminer | Out-Null
} catch {
  Write-Error "Docker compose failed. Is Docker Desktop running?"; Pop-Location; exit 1
}
Pop-Location

# Ensure venv python and dependencies
if (-not (Test-Path $PythonExe)) {
  Write-Host "[setup] Creating Python venv at $($BackendDir)\.venv ..." -ForegroundColor Yellow
  Push-Location $BackendDir
  python -m venv .venv
  Pop-Location
}

# Upgrade pip/setuptools/wheel and install project deps if imports fail
Write-Host "[setup] Verifying backend dependencies (fastapi, redis, sqlmodel)..." -ForegroundColor Yellow
try {
  & $PythonExe -c "import fastapi, redis, sqlmodel; print('deps-ok')" | Out-Null
} catch {
  Write-Host "[setup] Installing backend deps via pip editable..." -ForegroundColor Yellow
  Push-Location $BackendDir
  & $PythonExe -m pip install --upgrade pip setuptools wheel | Out-Null
  & $PythonExe -m pip install -e . | Out-Null
  Pop-Location
}

# Helper: start a process in a new window with working directory
function Start-DevProc {
  param(
    [Parameter(Mandatory)] [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory
  )
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  if ($ArgumentList) { $psi.Arguments = [string]::Join(' ', ($ArgumentList | ForEach-Object { if ($_ -match ' ') { '"' + $_ + '"' } else { $_ } })) }
  if ($WorkingDirectory) { $psi.WorkingDirectory = $WorkingDirectory }
  $psi.UseShellExecute = $true
  [System.Diagnostics.Process]::Start($psi)
}

$procs = @()

# Export runtime env overrides for host-mode
$env:REDIS_URL = 'redis://localhost:6379/0'
$env:ENABLE_METRICS = 'true'
# Database connection for host mode
$env:POSTGRES_SERVER = 'localhost'
$env:POSTGRES_PORT = '5432'
$env:POSTGRES_USER = 'postgres'
$env:POSTGRES_PASSWORD = 'changethis'
$env:POSTGRES_DB = 'app'
# You can also override these if needed:
# $env:FRONTEND_HOST = 'http://localhost:5174'
# $env:EXTERNAL_SELF_BASE_URL = 'http://localhost:8001'

# 2) Start FastAPI backend with Uvicorn on host (hot reload)
Write-Host "[2/4] Starting backend (Uvicorn on http://localhost:8001)..." -ForegroundColor Yellow
$backendArgs = @('-m','uvicorn','app.main:app','--reload','--host','0.0.0.0','--port','8001')
$backendProc = Start-DevProc -FilePath $PythonExe -ArgumentList $backendArgs -WorkingDirectory $BackendDir
$procs += @{ Name='backend'; P=$backendProc }
Write-Host ("  → backend PID {0}" -f $backendProc.Id)

# 3) Start RQ worker on host (default queue)
Write-Host "[3/4] Starting RQ worker (redis://localhost:6379/0, queue: default)..." -ForegroundColor Yellow
$rqArgs = @('-m','rq','worker','--url','redis://localhost:6379/0','default')
$rqProc = Start-DevProc -FilePath $PythonExe -ArgumentList $rqArgs -WorkingDirectory $BackendDir
$procs += @{ Name='rq-worker'; P=$rqProc }
Write-Host ("  → rq-worker PID {0}" -f $rqProc.Id)

# 4) Start Vite frontend (dev server on :5174)
Write-Host "[4/4] Starting Vite frontend (http://localhost:5174)..." -ForegroundColor Yellow
# Install deps if node_modules missing
if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
  Write-Host "[setup] Installing frontend dependencies (npm ci)..." -ForegroundColor Yellow
  Push-Location $FrontendDir
  npm ci | Out-Null
  Pop-Location
}
$viteArgs = @('run','dev')
$viteProc = Start-DevProc -FilePath 'npm' -ArgumentList $viteArgs -WorkingDirectory $FrontendDir
$procs += @{ Name='frontend'; P=$viteProc }
Write-Host ("  → frontend PID {0}" -f $viteProc.Id)

Write-Host ""; Write-Host "All services launched:" -ForegroundColor Cyan
foreach ($e in $procs) { Write-Host (" - {0} (PID {1})" -f $e.Name, $e.P.Id) }
Write-Host ""
Write-Host "Open:" -ForegroundColor DarkCyan
Write-Host " - Backend:  http://localhost:8001"
Write-Host " - Frontend: http://localhost:5174"
Write-Host " - Adminer:  http://localhost:8080"
Write-Host ""
Write-Host "TIP: Close the spawned windows to stop individual services." -ForegroundColor Yellow

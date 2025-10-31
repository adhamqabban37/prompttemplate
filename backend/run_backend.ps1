# Fast FastAPI Backend Launcher (Windows)
# Runs uvicorn with hot-reload on localhost:8001
# No Docker required for the backend itself

param(
    [switch]$SkipEnvCheck
)

$ErrorActionPreference = "Stop"
$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $backendRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

Write-Host "🚀 XenlixAI Backend Launcher" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

# Check venv exists
if (-not (Test-Path $venvPython)) {
    Write-Host "❌ Virtual environment not found at: $venvPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Run this first to create it:" -ForegroundColor Yellow
    Write-Host "  cd backend" -ForegroundColor White
    Write-Host "  python -m venv .venv" -ForegroundColor White
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host "  pip install -U pip setuptools wheel" -ForegroundColor White
    Write-Host "  pip install -e ." -ForegroundColor White
    exit 1
}

# Activate venv
Write-Host "✓ Activating virtual environment..." -ForegroundColor Green
& $venvActivate

# Set dev environment variables
if (-not $SkipEnvCheck) {
    Write-Host "✓ Setting environment variables..." -ForegroundColor Green
    
    $env:POSTGRES_SERVER = "localhost"
    $env:POSTGRES_PORT = "5432"
    $env:POSTGRES_USER = "app"
    $env:POSTGRES_PASSWORD = "changethis"
    $env:POSTGRES_DB = "app"
    $env:REDIS_URL = "redis://localhost:6379/0"
    $env:BACKEND_CORS_ORIGINS = '["http://localhost:5174","http://localhost:5173","http://localhost"]'
    $env:ENABLE_METRICS = "true"

    # Enable CrewAI by default for dev and set sensible LLM defaults
    $env:CREW_AI_ENABLED = "true"
    if (-not $env:MODEL -or $env:MODEL -eq "") { $env:MODEL = "ollama/llama3" }
    if (-not $env:OLLAMA_HOST -or $env:OLLAMA_HOST -eq "") { $env:OLLAMA_HOST = "http://localhost:11434" }
    if (-not $env:LLM_TIMEOUT_SECONDS -or $env:LLM_TIMEOUT_SECONDS -eq "") { $env:LLM_TIMEOUT_SECONDS = "15" }
    
    # Load secrets from root .env if present
    $rootEnv = Join-Path $backendRoot "..\..\.env"
    if (Test-Path $rootEnv) {
        Write-Host "  Loading secrets from .env..." -ForegroundColor DarkGray
        Get-Content $rootEnv | ForEach-Object {
            if ($_ -match '^PSI_API_KEY=(.+)') { $env:PSI_API_KEY = $matches[1] }
            if ($_ -match '^STRIPE_SECRET_KEY=(.+)') { $env:STRIPE_SECRET_KEY = $matches[1] }
            if ($_ -match '^STRIPE_WEBHOOK_SECRET=(.+)') { $env:STRIPE_WEBHOOK_SECRET = $matches[1] }
            if ($_ -match '^STRIPE_PRICE_ID=(.+)') { $env:STRIPE_PRICE_ID = $matches[1] }
            if ($_ -match '^CREW_AI_ENABLED=(.+)') { $env:CREW_AI_ENABLED = $matches[1] }
        }
    }
}

# Quick AI readiness probe (non-blocking)
try {
    $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri ($env:OLLAMA_HOST.TrimEnd('/') + "/api/tags")
    if ($resp.StatusCode -eq 200) {
        Write-Host "✓ CrewAI/Ollama reachable at $($env:OLLAMA_HOST)" -ForegroundColor Green
    } else {
        Write-Host "⚠️  CrewAI/Ollama responded with status $($resp.StatusCode) at $($env:OLLAMA_HOST)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  CrewAI/Ollama not reachable at $($env:OLLAMA_HOST). AI insights will fall back." -ForegroundColor Yellow
}

# Check Docker infra is running
Write-Host "✓ Checking Docker services..." -ForegroundColor Green
$dockerRunning = $false
try {
    # Check by service name (compose service is 'db') and by image ancestor as a fallback
    $dbByName = docker ps --filter "name=db" --filter "status=running" --format "{{.Names}}" 2>$null
    $dbByImage = docker ps --filter "ancestor=postgres" --filter "status=running" --format "{{.Names}}" 2>$null
    $redisCheck = docker ps --filter "name=redis" --filter "status=running" --format "{{.Names}}" 2>$null

    if ((($dbByName -or $dbByImage) -and $redisCheck)) {
        $dockerRunning = $true
        if ($dbByName -or $dbByImage) { Write-Host "  ✓ db: running" -ForegroundColor DarkGreen }
        if ($redisCheck) { Write-Host "  ✓ redis: running" -ForegroundColor DarkGreen }
    }
} catch {
    # Docker not available or services not running
}

if (-not $dockerRunning) {
    Write-Host ""
    Write-Host "⚠️  Docker infra not detected. Start it with:" -ForegroundColor Yellow
    Write-Host "  docker compose up -d db redis" -ForegroundColor White
    Write-Host "  (continuing without waiting; the app will fail if DB/Redis are required)" -ForegroundColor DarkGray
}

# Launch uvicorn
Write-Host ""
Write-Host "🌐 Starting FastAPI with uvicorn..." -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  Backend:  http://localhost:8001" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8001/docs" -ForegroundColor White
Write-Host "  Health:   http://localhost:8001/api/v1/utils/health-check/" -ForegroundColor White
Write-Host ""

Push-Location $backendRoot
& $venvPython -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
Pop-Location

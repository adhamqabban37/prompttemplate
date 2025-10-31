# 🔧 Fix Slow pip install and Rebuild Clean Virtual Environment
# For: c:\dev\projects-template\backend
# Windows PowerShell script to resolve hanging pip installs

$ErrorActionPreference = "Stop"
$backendRoot = "c:\dev\projects-template\backend"
$venvPath = Join-Path $backendRoot ".venv"

Write-Host "🔧 FastAPI Backend: Clean Venv Rebuild" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

# Step 1: Kill stuck pip/python processes
Write-Host "[1/6] Killing stuck pip/python processes..." -ForegroundColor Yellow
Get-Process | Where-Object {$_.Name -match "python|pip"} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Host "  ✓ Done" -ForegroundColor Green
Write-Host ""

# Step 2: Delete old venv
if (Test-Path $venvPath) {
    Write-Host "[2/6] Deleting old virtual environment..." -ForegroundColor Yellow
    Write-Host "  Path: $venvPath" -ForegroundColor DarkGray
    Remove-Item -Recurse -Force $venvPath -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    Write-Host "  ✓ Removed" -ForegroundColor Green
} else {
    Write-Host "[2/6] No old venv found (skipping)" -ForegroundColor DarkGray
}
Write-Host ""

# Step 3: Create fresh venv
Write-Host "[3/6] Creating fresh virtual environment..." -ForegroundColor Yellow
Push-Location $backendRoot
python -m venv .venv
if (-not $?) {
    Write-Host "  ❌ Failed to create venv. Is Python installed?" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Created at: $venvPath" -ForegroundColor Green
Write-Host ""

# Step 4: Upgrade pip/setuptools/wheel
Write-Host "[4/6] Upgrading pip, setuptools, wheel..." -ForegroundColor Yellow
$venvPython = Join-Path $venvPath "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip setuptools wheel --quiet
if (-not $?) {
    Write-Host "  ⚠️  Upgrade failed, but continuing..." -ForegroundColor Yellow
} else {
    Write-Host "  ✓ Upgraded" -ForegroundColor Green
}
Write-Host ""

# Step 5: Install dependencies FAST
Write-Host "[5/6] Installing project dependencies..." -ForegroundColor Yellow
Write-Host "  This may take 2-5 minutes on first run (downloading ML models)" -ForegroundColor DarkGray
Write-Host ""

# Option A: Use uv if available (10-100x faster)
$uvAvailable = Get-Command uv -ErrorAction SilentlyContinue
if ($uvAvailable) {
    Write-Host "  Using uv (fast installer)..." -ForegroundColor Cyan
    uv sync
    if ($?) {
        Write-Host "  ✓ Dependencies installed with uv" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  uv failed, falling back to pip..." -ForegroundColor Yellow
        & $venvPython -m pip install -e .
    }
} else {
    # Option B: Standard pip install
    Write-Host "  Using pip (standard installer)..." -ForegroundColor Cyan
    Write-Host "  TIP: Install 'uv' for 10x faster installs: pip install uv" -ForegroundColor DarkGray
    & $venvPython -m pip install -e .
    if (-not $?) {
        Write-Host "  ❌ pip install failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ Dependencies installed" -ForegroundColor Green
}
Write-Host ""

# Step 6: Verify installation
Write-Host "[6/6] Verifying installation..." -ForegroundColor Yellow
& $venvPython -c "import fastapi; import redis; import sqlmodel; print('✓ Core imports OK')"
if ($?) {
    Write-Host "  ✓ Backend ready!" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Some imports failed (may still work)" -ForegroundColor Yellow
}

Pop-Location
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Start Docker infra:" -ForegroundColor White
Write-Host "     docker compose up -d db redis" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  2. Run backend:" -ForegroundColor White
Write-Host "     cd backend" -ForegroundColor DarkGray
Write-Host "     .\run_backend.ps1" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  3. Visit:" -ForegroundColor White
Write-Host "     http://localhost:8001/docs" -ForegroundColor DarkGray
Write-Host ""

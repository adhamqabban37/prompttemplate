# XenlixAI Complete Health Check Script (Windows PowerShell)
# Usage: pwsh -NoLogo -NoProfile -File .\scripts\health-check.ps1

Write-Host "`n=== XENLIXAI SYSTEM HEALTH CHECK ===" -ForegroundColor Cyan

# 1) Container Status
Write-Host "`n[1/10] Containers status" -ForegroundColor Yellow
try {
  docker compose ps
} catch {
  Write-Host "Docker Compose not available or Docker not running" -ForegroundColor Red
  exit 1
}

# 2) Backend Health Endpoint
Write-Host "`n[2/10] Backend health endpoint" -ForegroundColor Yellow
try {
  $health = Invoke-RestMethod -Uri "http://localhost:8001/api/v1/utils/health-check/" -TimeoutSec 5
  Write-Host ("✓ Backend health: {0}" -f $health.status) -ForegroundColor Green
} catch {
  Write-Host "✗ Backend health check failed" -ForegroundColor Red
}

# 3) Database Ready
Write-Host "`n[3/10] PostgreSQL ready?" -ForegroundColor Yellow
$pg = docker compose exec -T db pg_isready -U app 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Host "✓ Database is ready" -ForegroundColor Green
} else {
  Write-Host "✗ Database not ready" -ForegroundColor Red
}

# 4) Redis Alive
Write-Host "`n[4/10] Redis ping" -ForegroundColor Yellow
$redisPing = docker compose exec -T redis redis-cli ping 2>$null
if ($redisPing -match "PONG") {
  Write-Host "✓ Redis is responding" -ForegroundColor Green
} else {
  Write-Host "✗ Redis not responding" -ForegroundColor Red
}

# 5) Ports
Write-Host "`n[5/10] Ports open" -ForegroundColor Yellow
$ports = 8001, 5432, 6379, 8080, 80, 5173, 5174
foreach ($p in $ports) {
  $r = Test-NetConnection -ComputerName localhost -Port $p -WarningAction SilentlyContinue
  Write-Host ("Port {0}: {1}" -f $p, ($r.TcpTestSucceeded ? 'open' : 'closed'))
}

# 6) Backend Env Snapshot
Write-Host "`n[6/10] Backend environment (key vars)" -ForegroundColor Yellow
try {
  docker compose exec -T backend env \
    | Select-String -Pattern "DATABASE_URL|POSTGRES|REDIS_URL|PSI_API_KEY|CREW_AI_ENABLED" \
    | ForEach-Object { $_.ToString() }
} catch {}

# 7) Resource Usage
Write-Host "`n[7/10] Container resource usage (one-shot)" -ForegroundColor Yellow
try {
  docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
} catch {}

# 8) Recent Errors in Logs
Write-Host "`n[8/10] Recent errors (last 150 lines across services)" -ForegroundColor Yellow
try {
  docker compose logs --tail 150 2>&1 | Select-String -Pattern "ERROR|CRITICAL|Exception|Traceback"
} catch {}

# 9) Docker Disk Usage
Write-Host "`n[9/10] Docker disk usage" -ForegroundColor Yellow
try {
  docker system df
} catch {}

# 10) Quick Scan Job Test (optional)
Write-Host "`n[10/10] Quick scan job test (enqueue)" -ForegroundColor Yellow
try {
  $resp = Invoke-RestMethod -Method POST -Uri "http://localhost:8001/api/v1/scan-jobs" -ContentType "application/json" -Body '{"url":"https://example.com"}' -TimeoutSec 10
  if ($resp.id) {
    Write-Host ("✓ Enqueued scanId: {0}" -f $resp.id) -ForegroundColor Green
    $scanId = $resp.id
    1..4 | ForEach-Object {
      Start-Sleep -Seconds 2
      try {
        $s = Invoke-RestMethod -Uri "http://localhost:8001/api/v1/scan-jobs/$scanId/status" -TimeoutSec 5
        Write-Host ("  Status: {0}  Progress: {1}" -f $s.status, $s.progress)
      } catch {
        Write-Host "  Status check failed"
      }
    }
  } else {
    Write-Host "✗ Enqueue failed" -ForegroundColor Red
  }
} catch {
  Write-Host "✗ Scan job test failed" -ForegroundColor Red
}

Write-Host "`n=== HEALTH CHECK COMPLETE ===" -ForegroundColor Cyan

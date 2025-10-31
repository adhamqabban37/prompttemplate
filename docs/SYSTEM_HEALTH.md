# XenlixAI — System Health Check & Troubleshooting

This guide is adapted to this repository’s setup:

- Backend on http://localhost:8001 (container exposes 8000 → host 8001)
- Services: backend, db (PostgreSQL), redis, proxy (Traefik), adminer, frontend, frontend-dev, worker
- Use PowerShell on Windows and `docker compose`

## ✅ Current status (2025-10-30)

- Containers: db and redis are running via Docker Compose.
- Backend: started on http://localhost:8001 and responding.
  - Health-check: 200 OK
  - Metrics: 200 OK at /metrics
- Note: The backend launcher was updated to correctly detect the Compose service name `db` and no longer blocks waiting for input if Docker isn't running.

## 🚀 QUICK HEALTH CHECK

### 1) Containers status

```powershell
# All containers and status
docker compose ps

# Red flags:
# - Any service Exit/Restarting/Unhealthy
# - Missing core services: backend, db, redis, proxy, adminer
```

### 2) Health of specific services

```powershell
# Backend API health
Invoke-WebRequest -Uri "http://localhost:8001/api/v1/utils/health-check/" -TimeoutSec 5 \
  | Select-Object -ExpandProperty Content

# PostgreSQL ready?
docker compose exec -T db pg_isready -U app

# Redis alive?
docker compose exec -T redis redis-cli ping
```

### 3) Ports open

```powershell
# Check commonly used ports
$ports = 8001, 5432, 6379, 8080, 80, 5173, 5174
$ports | ForEach-Object {
  $r = Test-NetConnection -ComputerName localhost -Port $_ -WarningAction SilentlyContinue
  "Port $_: " + ($r.TcpTestSucceeded ? 'open' : 'closed')
}
```

---

## 📋 DIAGNOSTICS

### 4) Logs (recent)

```powershell
# Backend (last 100 lines)
docker compose logs backend --tail 100

# All services (last 50 lines)
docker compose logs --tail 50

# Follow everything (Ctrl+C to stop)
docker compose logs -f
```

Look for:

- GOOD: "Application startup complete", 200 OK on health-check, PSI cache hits
- BAD: sqlalchemy OperationalError, redis ConnectionError, timeouts, repeated restarts

### 5) Environment inside backend

```powershell
docker compose exec -T backend env \
  | Select-String -Pattern "DATABASE_URL|POSTGRES|REDIS_URL|PSI_API_KEY|CREW_AI_ENABLED"
```

Common issues:

- DATABASE*URL or POSTGRES*\* pointing to localhost (should point to db)
- REDIS_URL missing
- PSI_API_KEY empty (PSI disabled)

### 6) Resource usage & disk

```powershell
# One-shot stats
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Docker disk usage
docker system df
```

Symptoms:

- High CPU/Mem on backend/worker
- Disk >80% full → prune unused artifacts

### 7) Database checks

```powershell
# Connect to Postgres shell if needed
docker compose exec -T db psql -U app -d app -c "\dt"
# Example quick checks
# docker compose exec -T db psql -U app -d app -c "SELECT COUNT(*) FROM scanjob;"
```

### 8) Redis checks

```powershell
# Basic info
docker compose exec -T redis redis-cli INFO memory | Select-String used_memory_human
# List keys (if not huge)
docker compose exec -T redis redis-cli KEYS "*" | Select-Object -First 50
```

---

## 🔧 ENDPOINT TESTS

### Health

```powershell
Invoke-WebRequest -Uri "http://localhost:8001/api/v1/utils/health-check/" -TimeoutSec 5 \
  | Select-Object -ExpandProperty Content
```

### Job-based scan (fast enqueue)

```powershell
# Start a scan (returns immediately)
$resp = Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8001/api/v1/scan-jobs" `
  -ContentType "application/json" `
  -Body '{"url":"https://example.com"}'
$scanId = $resp.id
"Enqueued scanId: $scanId"

# Poll status (2-3 times)
1..5 | ForEach-Object {
  Start-Sleep -Seconds 2
  $s = Invoke-RestMethod -Uri "http://localhost:8001/api/v1/scan-jobs/$scanId/status"
  "Status: $($s.status) Progress: $($s.progress)"
}

# Optional: fetch full when done
# Invoke-RestMethod -Uri "http://localhost:8001/api/v1/scan-jobs/$scanId/full"
```

### Billing

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/api/v1/billing/me"
```

---

## 🐛 COMMON FIXES

- Backend won’t start:

  - `docker compose logs backend --tail 200`
  - If DB not ready: `docker compose restart backend`
  - Apply migrations if needed: `docker compose exec -T backend alembic upgrade head`

- DB errors:

  - Check logs: `docker compose logs db --tail 100`
  - Test: `docker compose exec -T db pg_isready -U app`

- Redis errors:

  - `docker compose logs redis --tail 100`
  - `docker compose restart redis`

- Frontend can’t reach backend:

  - Health: `Invoke-WebRequest http://localhost:8001/api/v1/utils/health-check/`
  - CORS: ensure `BACKEND_CORS_ORIGINS` includes `http://localhost:5173` and `http://localhost:5174`
  - Vite proxy already forwards `/api` → `http://localhost:8001`

- Slow builds:
  - `docker builder prune -af`
  - Rebuild specific service with no cache: `docker compose build --no-cache backend`

---

## 📜 AUTOMATED HEALTH SCRIPT

Save and run: `scripts/health-check.ps1`

```powershell
pwsh -NoLogo -NoProfile -File .\scripts\health-check.ps1
```

This performs the quick checks, prints statuses, and highlights likely issues.

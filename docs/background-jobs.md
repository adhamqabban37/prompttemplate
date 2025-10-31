# Background Job Queue with RQ

## Overview

XenlixAI uses **RQ (Redis Queue)** for asynchronous background job processing. This enables:

- Non-blocking API responses for long-running scans
- Horizontal scaling of worker processes
- Job retry and failure handling
- Progress tracking and status updates

## Architecture

```
[Frontend] → [API] → [Redis Queue] → [Worker(s)] → [Database]
                ↓                           ↓
            [Immediate Response]    [Background Processing]
```

## Job Types

### 1. Scan Job (`process_scan_job`)

**Purpose**: Full scan pipeline execution (HTML fetch, PSI, KeyBERT, AI insights)

**Parameters**:

- `scan_id` (str): UUID of ScanJob database row
- `url` (str): Target URL to scan
- `user_id` (str | None): Optional user ID for premium features

**Duration**: 10-60 seconds depending on URL complexity and AI timeout

**Status Flow**:

```
QUEUED → RUNNING (CRAWL → PARSE → ANALYZE → GENERATE) → TEASER_READY → FULL_READY
```

**Error States**:

- `ERROR_VALIDATION`: SSRF or URL validation failed
- `ERROR_CRAWL`: HTML fetch timeout/error
- `ERROR_ANALYZE`: Processing/extraction error

### 2. Cleanup Job (`cleanup_expired_jobs`)

**Purpose**: Remove expired scan jobs from database

**Schedule**: Runs hourly via RQ scheduler

**TTL**: Configurable via `SCAN_JOB_TTL_SECONDS` (default 24 hours)

## Worker Management

### Starting Workers Locally

**Docker Compose** (recommended for local dev):

```bash
docker compose up -d worker
```

**Manual**:

```bash
# From backend directory
python -m app.worker
```

**RQ CLI** (advanced):

```bash
rq worker xenlixai_queue --with-scheduler
```

### Scaling Workers

**Docker Compose**:

```bash
docker compose up -d --scale worker=4
```

**Production (systemd)**:

```ini
[Unit]
Description=XenlixAI RQ Worker %i
After=redis.service postgresql.service

[Service]
Type=simple
User=xenlixai
WorkingDirectory=/app/backend
Environment="REDIS_URL=redis://localhost:6379/0"
ExecStart=/app/.venv/bin/python -m app.worker
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable multiple workers:

```bash
sudo systemctl enable xenlixai-worker@{1..4}.service
sudo systemctl start xenlixai-worker@{1..4}.service
```

## Job Enqueuing

### From API Route

```python
from app.worker import get_queue

queue = get_queue()
job = queue.enqueue(
    "app.worker.process_scan_job",
    scan_id=str(scan_job.id),
    url=url,
    user_id=str(current_user.id) if current_user else None,
    job_timeout="5m",  # Kill job after 5 minutes
    result_ttl=3600,   # Keep result for 1 hour
)
logger.info(f"Enqueued job {job.id} for scan {scan_job.id}")
```

### Job Options

- `job_timeout`: Maximum execution time (e.g., "5m", "300s")
- `result_ttl`: How long to keep job result in Redis (seconds)
- `failure_ttl`: How long to keep failed job data (seconds)
- `ttl`: Time-to-live for the job itself before execution
- `depends_on`: Parent job that must complete first

### Scheduled Jobs

```python
from rq import Scheduler

scheduler = Scheduler(queue=get_queue())
scheduler.cron(
    "0 * * * *",  # Every hour
    func="app.worker.cleanup_expired_jobs",
    queue_name="xenlixai_queue",
)
```

## Monitoring

### Queue Depth

```bash
redis-cli LLEN rq:queue:xenlixai_queue
```

### Failed Jobs

```bash
redis-cli LLEN rq:queue:failed
```

### Worker Status

```bash
rq info --url redis://localhost:6379/0
```

### RQ Dashboard (Web UI)

```bash
pip install rq-dashboard
rq-dashboard --redis-url redis://localhost:6379/0
```

Access at `http://localhost:9181`

### Prometheus Metrics

See [metrics.md](./metrics.md) for:

- `xenlixai_job_queue_size` - Current queue depth
- `xenlixai_background_jobs_total` - Job counts by status
- `xenlixai_background_job_duration_seconds` - Job duration histogram

## Error Handling

### Automatic Retries

```python
queue.enqueue(
    "app.worker.process_scan_job",
    ...,
    retry=Retry(max=3, interval=[10, 30, 60]),  # Retry with backoff
)
```

### Manual Retry

```bash
rq requeue --queue xenlixai_queue <job_id>
```

### Failed Job Inspection

```python
from rq import Queue
from rq.job import Job

queue = get_queue()
failed = queue.failed_job_registry

for job_id in failed.get_job_ids():
    job = Job.fetch(job_id, connection=queue.connection)
    print(f"Job {job_id}: {job.exc_info}")
```

## Best Practices

### 1. Idempotency

Jobs should be safe to run multiple times:

```python
# Check if already processed
if job.status in ("FULL_READY", "ERROR_ANALYZE"):
    logger.info(f"Job {scan_id} already processed")
    return {"status": job.status}
```

### 2. Progress Updates

Update database incrementally:

```python
job.step = "PARSE"
job.progress = 30
session.add(job)
session.commit()  # Frontend can poll for updates
```

### 3. Timeouts

Always set job timeouts to prevent hung jobs:

```python
queue.enqueue(..., job_timeout="5m")
```

### 4. Resource Limits

Limit concurrent workers based on:

- CPU cores (for KeyBERT)
- Memory (for sentence-transformers models)
- External API rate limits (PSI, LLM)

Recommended: 2-4 workers per server

### 5. Graceful Shutdown

Workers handle SIGTERM/SIGINT cleanly:

```python
# Docker stop sends SIGTERM; worker finishes current job
docker compose stop worker  # Waits up to 10s
```

## Troubleshooting

### Queue Not Processing

**Check Redis connection**:

```bash
docker compose exec backend python -c "from app.worker import get_redis_connection; print(get_redis_connection().ping())"
```

**Check worker logs**:

```bash
docker compose logs -f worker
```

**Restart worker**:

```bash
docker compose restart worker
```

### Jobs Timing Out

- Increase `job_timeout` value
- Reduce `LLM_TIMEOUT_SECONDS` for AI insights
- Optimize KeyBERT timeout (`KEYPHRASES_TIMEOUT_MS`)

### Memory Issues

- Limit concurrent workers
- Use Redis maxmemory policy: `allkeys-lru`
- Monitor with `docker stats`

### Stale Jobs

**Clear all pending jobs** (caution!):

```bash
redis-cli DEL rq:queue:xenlixai_queue
```

**Remove failed jobs**:

```bash
redis-cli DEL rq:queue:failed
```

## Development vs Production

### Local Development

- Use `docker-compose.override.yml` worker service
- Single worker sufficient
- RQ Dashboard for debugging

### Production

- Multiple worker instances (systemd or k8s)
- RQ scheduler for cleanup jobs
- Prometheus metrics + alerts
- Sentry integration for error tracking
- Redis persistence (AOF or RDB snapshots)

## Future Enhancements

- [ ] Priority queues (premium users get faster processing)
- [ ] Job dependencies (multi-page scans)
- [ ] Periodic scans (cron-like scheduling)
- [ ] Webhook callbacks (notify external systems)
- [ ] Dead letter queue (forensics)

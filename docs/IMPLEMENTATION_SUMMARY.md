# Background Queue and Metrics Implementation Summary

## Overview

Successfully added Redis-based background job queue (RQ) and Prometheus metrics instrumentation to XenlixAI backend.

## Changes Made

### 1. Dependencies Added (`backend/pyproject.toml`)

```toml
"rq>=1.15.0,<2.0.0",
"prometheus-client>=0.19.0,<1.0.0",
"prometheus-fastapi-instrumentator>=6.1.0,<7.0.0",
```

### 2. New Files Created

#### `backend/app/worker.py`

- RQ worker implementation for background job processing
- `process_scan_job()`: Full scan pipeline execution (HTML, PSI, KeyBERT, AI)
- `cleanup_expired_jobs()`: Scheduled cleanup of old scan jobs
- Worker entry point and queue management

#### `backend/app/metrics.py`

- Comprehensive Prometheus metrics instrumentation
- HTTP request/response metrics (auto-instrumented)
- Scan pipeline stage metrics (html_fetch, psi, keyphrases, ai, total)
- External service metrics (PSI, LLM, KeyBERT latencies)
- Background job metrics (queue depth, job duration)
- Cache hit/miss rates
- Business metrics (premium conversions, active jobs)
- Context managers for easy tracking: `track_scan_request()`, `track_psi_call()`, etc.

#### `docs/metrics.md`

- Complete Prometheus metrics documentation
- PromQL query examples
- Grafana dashboard setup guide
- Alert rule recommendations

#### `docs/background-jobs.md`

- RQ background queue architecture
- Job types and lifecycle
- Worker management (Docker, systemd)
- Monitoring and troubleshooting guide

### 3. Modified Files

#### `backend/app/main.py`

- Added Prometheus instrumentator middleware
- Exposed `/metrics` endpoint
- Initialized app info metric at startup

#### `backend/app/api/routes/scan_jobs.py`

- Integrated RQ job enqueuing in `start_scan()` endpoint
- Fallback to soft-progress if worker unavailable
- Added metrics tracking for background jobs
- Queue depth monitoring

#### `backend/app/api/routes/scan.py`

- Wrapped scan requests with metrics context manager
- Added stage-by-stage timing instrumentation
- Error tracking by type (SSRF, timeout, etc.)
- Fixed GET endpoint to accept Request parameter

#### `.env`

- Added `RQ_WORKER_COUNT=2`
- Added `RQ_QUEUE_NAME=xenlixai_queue`
- Added `ENABLE_METRICS=true`
- Clarified Redis usage for caching + job queue

#### `docker-compose.override.yml`

- Added `worker` service for RQ background processing
- Shared ML model cache volume between backend and worker
- Environment variable passthrough for worker

## Architecture

### Request Flow (Async Jobs)

```
1. POST /api/v1/scan-jobs
   ↓
2. Create ScanJob row (status=QUEUED)
   ↓
3. Enqueue background job to Redis
   ↓
4. Return scanId immediately (non-blocking)
   ↓
5. Worker picks up job from queue
   ↓
6. Worker executes full pipeline:
   - HTML fetch (CRAWL)
   - Content extraction (PARSE)
   - PSI metrics (ANALYZE)
   - KeyBERT + AI insights (GENERATE)
   ↓
7. Worker updates ScanJob status → FULL_READY
   ↓
8. Frontend polls GET /scan-jobs/{scanId}/status
   ↓
9. Frontend fetches teaser/full payloads
```

### Metrics Collection

```
[FastAPI App]
    ↓
[Instrumentator Middleware] → Automatic HTTP metrics
    ↓
[Custom Metrics] → Business-specific metrics
    ↓
[/metrics Endpoint] → Prometheus scrapes here
    ↓
[Prometheus Server] → Time-series storage
    ↓
[Grafana] → Visualization & alerting
```

## Key Features

### Background Queue (RQ)

- **Non-blocking API**: Immediate response for long-running scans
- **Horizontal scaling**: Multiple workers can process jobs concurrently
- **Progress tracking**: Database updates during job execution
- **Failure handling**: Automatic retries with backoff
- **Job timeout**: Configurable per-job timeout (default 5 minutes)
- **Result TTL**: Temporary result storage in Redis

### Prometheus Metrics

- **HTTP metrics**: Request count, latency histograms, in-progress requests
- **Scan metrics**: Success/error rates, stage-by-stage duration
- **External services**: PSI, LLM, KeyBERT call tracking
- **Queue metrics**: Job count, queue depth, worker throughput
- **Cache metrics**: Hit/miss rates for PSI and KeyBERT
- **Business metrics**: Premium conversions, active scan jobs

## Environment Variables

```bash
# Background Worker
RQ_WORKER_COUNT=2
RQ_QUEUE_NAME=xenlixai_queue

# Prometheus Metrics
ENABLE_METRICS=true

# Redis (existing, now also used for RQ)
REDIS_URL=redis://redis:6379/0
```

## Deployment Steps

### 1. Install Dependencies

```bash
cd backend
uv sync
# or
pip install -r requirements.txt
```

### 2. Start Services (Docker Compose)

```bash
docker compose up -d --build backend worker
```

### 3. Verify Worker

```bash
docker compose logs -f worker
# Should see: "Starting RQ worker for xenlixai_queue..."
```

### 4. Verify Metrics

```bash
curl http://localhost:8001/metrics
# Should return Prometheus metrics in text format
```

### 5. Test Background Job

```bash
curl -X POST http://localhost:8001/api/v1/scan-jobs \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
# Returns: {"scanId": "...", "status": "QUEUED"}

# Poll status
curl http://localhost:8001/api/v1/scan-jobs/{scanId}/status
# Progress: QUEUED → RUNNING → TEASER_READY → FULL_READY
```

## Monitoring Setup

### Prometheus (Local)

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "xenlixai"
    static_configs:
      - targets: ["host.docker.internal:8001"]
```

```bash
docker run -d -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

### Grafana Dashboards

1. Request rate and latency (p50, p95, p99)
2. Error rates by endpoint and type
3. Scan pipeline stage breakdown
4. External service health (PSI, LLM latency)
5. Queue depth and worker throughput
6. Cache hit rates

### Alert Rules

- High error rate (> 5% over 5m)
- Slow scan times (p95 > 30s)
- Queue backlog (depth > 100)
- Worker failures

## Performance Considerations

### Worker Scaling

- **CPU-bound**: KeyBERT model inference
- **I/O-bound**: PSI API calls, LLM requests
- **Recommended**: 2-4 workers per server
- **Memory**: ~2GB per worker (ML models)

### Redis Tuning

- **Max memory**: 2GB minimum
- **Eviction policy**: `allkeys-lru` for cache
- **Persistence**: AOF for job data durability
- **Connection pool**: 10 connections per worker

### Metrics Cardinality

- **URL labels**: Normalize to prevent explosion
- **Status codes**: Group 2xx, 4xx, 5xx
- **Queue names**: Limited to known queues

## Troubleshooting

### Worker Not Processing Jobs

```bash
# Check Redis connection
docker compose exec backend python -c "from app.worker import get_redis_connection; print(get_redis_connection().ping())"

# Check queue depth
redis-cli LLEN rq:queue:xenlixai_queue

# Restart worker
docker compose restart worker
```

### Metrics Not Appearing

```bash
# Check endpoint
curl http://localhost:8001/metrics | head -n 20

# Check ENABLE_METRICS env var
docker compose exec backend env | grep ENABLE_METRICS

# Restart backend
docker compose restart backend
```

### High Memory Usage

```bash
# Check worker memory
docker stats

# Reduce worker count
docker compose up -d --scale worker=1

# Clear Redis cache
redis-cli FLUSHDB
```

## Next Steps

1. **Start Docker**: Ensure Docker Desktop is running
2. **Rebuild**: `docker compose build backend worker`
3. **Start services**: `docker compose up -d backend worker`
4. **Test scan job**: Create scan job via API and monitor in logs
5. **View metrics**: `curl http://localhost:8001/metrics`
6. **Optional**: Set up Prometheus + Grafana for visualization

## Code Examples

### Using Metrics in New Endpoints

```python
from app.metrics import track_scan_request, track_scan_stage

@router.post("/my-endpoint")
def my_endpoint():
    with track_scan_request("/api/v1/my-endpoint") as ctx:
        start = time.time()

        # Do work
        result = perform_analysis()

        # Track stage
        duration = time.time() - start
        track_scan_stage("/api/v1/my-endpoint", "analysis", duration)

        # Mark success
        ctx["result"] = "success"

        return result
```

### Enqueueing Custom Jobs

```python
from app.worker import get_queue

queue = get_queue()
job = queue.enqueue(
    "app.worker.my_custom_job",
    arg1="value",
    job_timeout="10m",
    result_ttl=7200,
)
```

## Documentation References

- [Metrics Guide](./docs/metrics.md)
- [Background Jobs Guide](./docs/background-jobs.md)
- [RQ Documentation](https://python-rq.org/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)

## Summary of Benefits

✅ **Non-blocking API**: Scans run in background, immediate response  
✅ **Horizontal scaling**: Add more workers to handle load  
✅ **Observability**: Rich metrics for performance tuning  
✅ **Error tracking**: Detailed error classification  
✅ **Cache monitoring**: Visibility into PSI and KeyBERT cache effectiveness  
✅ **Production-ready**: Battle-tested libraries (RQ, Prometheus)  
✅ **Developer-friendly**: Context managers for easy instrumentation

# Metrics and Monitoring

## Overview

XenlixAI includes comprehensive Prometheus metrics instrumentation for monitoring API performance, scan pipeline health, and external service dependencies.

## Metrics Endpoint

- **URL**: `http://localhost:8001/metrics`
- **Format**: Prometheus text exposition format
- **Access**: Public (consider adding authentication in production)

## Key Metrics Categories

### 1. HTTP Request Metrics (Auto-instrumented)

```
# Request latency histogram
http_request_duration_seconds{method="GET",endpoint="/api/v1/scan",status_code="200"}

# Request count
http_requests_total{method="POST",endpoint="/api/v1/scan",status_code="200"}

# In-progress requests
http_requests_inprogress{method="POST",endpoint="/api/v1/scan"}
```

### 2. Scan Pipeline Metrics

```
# Total scan requests by result
xenlixai_scan_requests_total{endpoint="/api/v1/scan",result="success"}

# Scan duration by stage
xenlixai_scan_duration_seconds{endpoint="/api/v1/scan",stage="html_fetch"}
xenlixai_scan_duration_seconds{endpoint="/api/v1/scan",stage="psi"}
xenlixai_scan_duration_seconds{endpoint="/api/v1/scan",stage="keyphrases"}
xenlixai_scan_duration_seconds{endpoint="/api/v1/scan",stage="ai"}
xenlixai_scan_duration_seconds{endpoint="/api/v1/scan",stage="total"}

# Scan errors by type
xenlixai_scan_errors_total{error_type="ssrf"}
xenlixai_scan_errors_total{error_type="timeout"}
```

### 3. External Service Metrics

```
# PSI API calls
xenlixai_psi_requests_total{result="success"}
xenlixai_psi_requests_total{result="cache_hit"}
xenlixai_psi_duration_seconds

# LLM/CrewAI calls
xenlixai_llm_requests_total{model="ollama/llama3.2:3b",result="success"}
xenlixai_llm_duration_seconds{model="ollama/llama3.2:3b"}

# KeyBERT extraction
xenlixai_keyphrases_requests_total{result="success"}
xenlixai_keyphrases_duration_seconds
```

### 4. Background Job Metrics

```
# Background job tracking
xenlixai_background_jobs_total{job_type="scan_job",result="completed"}
xenlixai_background_job_duration_seconds{job_type="scan_job"}

# Queue depth
xenlixai_job_queue_size{queue_name="xenlixai_queue"}
```

### 5. Cache Metrics

```
# Cache hit/miss rates
xenlixai_cache_requests_total{cache_type="psi",result="hit"}
xenlixai_cache_requests_total{cache_type="keyphrases",result="miss"}
```

### 6. Business Metrics

```
# Premium conversions
xenlixai_premium_conversions_total{source="stripe"}

# Active scan jobs by status
xenlixai_scan_jobs_active{status="RUNNING"}
```

## Querying with PromQL

### Average scan duration (last 5 minutes)

```promql
rate(xenlixai_scan_duration_seconds_sum{stage="total"}[5m])
/
rate(xenlixai_scan_duration_seconds_count{stage="total"}[5m])
```

### 95th percentile scan latency

```promql
histogram_quantile(0.95,
  rate(xenlixai_scan_duration_seconds_bucket{stage="total"}[5m])
)
```

### PSI cache hit rate

```promql
sum(rate(xenlixai_psi_requests_total{result="cache_hit"}[5m]))
/
sum(rate(xenlixai_psi_requests_total[5m]))
```

### Error rate (last 5 minutes)

```promql
sum(rate(xenlixai_scan_errors_total[5m])) by (error_type)
```

### Background job success rate

```promql
sum(rate(xenlixai_background_jobs_total{result="completed"}[5m]))
/
sum(rate(xenlixai_background_jobs_total{result=~"completed|failed"}[5m]))
```

## Grafana Dashboard Setup

1. **Add Prometheus data source**
   - URL: `http://localhost:9090` (if running Prometheus locally)
2. **Create panels for key metrics**:

   - Request rate and latency
   - Error rates by type
   - Scan pipeline stage breakdown
   - External service health (PSI, LLM latency)
   - Queue depth and worker throughput

3. **Alert rules**:
   - High error rate (> 5% over 5m)
   - Slow scan times (p95 > 30s)
   - Queue backlog (depth > 100)
   - External service failures

## Local Development

### View metrics

```bash
curl http://localhost:8001/metrics
```

### Run Prometheus locally

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

### Run Grafana locally

```bash
docker run -d -p 3000:3000 grafana/grafana
```

Access Grafana at `http://localhost:3000` (admin/admin)

## Production Recommendations

1. **Authentication**: Add bearer token auth to `/metrics` endpoint
2. **Cardinality**: Limit label values (e.g., normalize URLs, cap queue names)
3. **Retention**: Configure Prometheus retention (default 15 days)
4. **Alerting**: Set up Alertmanager for critical alerts
5. **Dashboards**: Pre-build Grafana dashboards and export as JSON

## Structured Logging Integration

All scan requests include structured JSON logs with correlation IDs:

```json
{
  "event": "scan_start",
  "scan_id": "a1b2c3d4",
  "url": "https://example.com",
  "timestamp": 1698765432.123
}
```

Combine metrics with logs for deep observability:

- Metrics: quantitative performance data
- Logs: qualitative context and error details

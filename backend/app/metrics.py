"""Prometheus metrics instrumentation for XenlixAI.

Provides:
- Request/response latency histograms
- Error rate counters
- Background job metrics
- External service (PSI, LLM, Redis) latency tracking
- Custom business metrics (scans per endpoint, cache hit rates, etc.)

Usage:
    from app.metrics import (
        track_scan_request,
        track_psi_call,
        track_llm_call,
        SCAN_REQUESTS_TOTAL,
    )
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Generator

from prometheus_client import Counter, Histogram, Gauge, Info

# ============================
# Core HTTP Metrics
# ============================

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint", "status_code"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

# ============================
# Scan Pipeline Metrics
# ============================

SCAN_REQUESTS_TOTAL = Counter(
    "xenlixai_scan_requests_total",
    "Total scan requests by endpoint and result",
    ["endpoint", "result"],  # result: success | error | timeout
)

SCAN_DURATION = Histogram(
    "xenlixai_scan_duration_seconds",
    "Scan pipeline duration in seconds",
    ["endpoint", "stage"],  # stage: html_fetch | psi | keyphrases | ai | rules | total
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0),
)

SCAN_ERRORS = Counter(
    "xenlixai_scan_errors_total",
    "Scan errors by type",
    ["error_type"],  # ssrf | timeout | http_error | parse_error | llm_error
)

# ============================
# External Service Metrics
# ============================

PSI_REQUESTS = Counter(
    "xenlixai_psi_requests_total",
    "PSI API requests",
    ["result"],  # success | error | cache_hit
)

PSI_LATENCY = Histogram(
    "xenlixai_psi_duration_seconds",
    "PSI API call duration",
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0),
)

LLM_REQUESTS = Counter(
    "xenlixai_llm_requests_total",
    "LLM/CrewAI requests",
    ["model", "result"],  # result: success | timeout | error | disabled
)

LLM_LATENCY = Histogram(
    "xenlixai_llm_duration_seconds",
    "LLM call duration",
    ["model"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0),
)

KEYPHRASES_REQUESTS = Counter(
    "xenlixai_keyphrases_requests_total",
    "KeyBERT extraction requests",
    ["result"],  # success | timeout | error | cache_hit
)

KEYPHRASES_LATENCY = Histogram(
    "xenlixai_keyphrases_duration_seconds",
    "KeyBERT extraction duration",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
)

# ============================
# Background Job Metrics
# ============================

BACKGROUND_JOBS_TOTAL = Counter(
    "xenlixai_background_jobs_total",
    "Background jobs enqueued",
    ["job_type", "result"],  # result: enqueued | started | completed | failed
)

BACKGROUND_JOB_DURATION = Histogram(
    "xenlixai_background_job_duration_seconds",
    "Background job duration",
    ["job_type"],
    buckets=(1.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0, 300.0),
)

JOB_QUEUE_SIZE = Gauge(
    "xenlixai_job_queue_size",
    "Current job queue depth",
    ["queue_name"],
)

# ============================
# Cache Metrics
# ============================

CACHE_REQUESTS = Counter(
    "xenlixai_cache_requests_total",
    "Cache requests",
    ["cache_type", "result"],  # cache_type: psi | keyphrases | lighthouse; result: hit | miss
)

# ============================
# Business Metrics
# ============================

PREMIUM_CONVERSIONS = Counter(
    "xenlixai_premium_conversions_total",
    "Premium upgrade events",
    ["source"],  # source: stripe | manual
)

SCAN_JOBS_ACTIVE = Gauge(
    "xenlixai_scan_jobs_active",
    "Active scan jobs by status",
    ["status"],  # QUEUED | RUNNING | TEASER_READY | FULL_READY | ERROR_*
)

# ============================
# Application Info
# ============================

APP_INFO = Info("xenlixai_app", "Application version and environment info")

# Initialize app info (call once at startup)
def initialize_app_info(version: str = "0.1.0", environment: str = "local"):
    """Set application info metric."""
    APP_INFO.info({"version": version, "environment": environment})


# ============================
# Tracking Helpers
# ============================


@contextmanager
def track_scan_request(endpoint: str) -> Generator[dict, None, None]:
    """Track scan request with automatic timing and error handling.

    Usage:
        with track_scan_request("/api/v1/scan") as ctx:
            # ... perform scan ...
            ctx["result"] = "success"
    """
    start = time.time()
    context = {"result": "error"}  # default to error unless explicitly set

    try:
        yield context
    finally:
        duration = time.time() - start
        result = context.get("result", "error")
        SCAN_REQUESTS_TOTAL.labels(endpoint=endpoint, result=result).inc()
        SCAN_DURATION.labels(endpoint=endpoint, stage="total").observe(duration)


@contextmanager
def track_psi_call() -> Generator[dict, None, None]:
    """Track PSI API call timing and result.

    Usage:
        with track_psi_call() as ctx:
            psi_data = fetch_psi(url)
            ctx["result"] = "success"  # or "cache_hit"
    """
    start = time.time()
    context = {"result": "error"}

    try:
        yield context
    finally:
        duration = time.time() - start
        result = context.get("result", "error")
        PSI_REQUESTS.labels(result=result).inc()
        if result != "cache_hit":
            PSI_LATENCY.observe(duration)


@contextmanager
def track_llm_call(model: str) -> Generator[dict, None, None]:
    """Track LLM call timing and result.

    Usage:
        with track_llm_call("ollama/llama3.2:3b") as ctx:
            insights = generate_recommendations(...)
            ctx["result"] = "success"  # or "timeout" | "disabled"
    """
    start = time.time()
    context = {"result": "error"}

    try:
        yield context
    finally:
        duration = time.time() - start
        result = context.get("result", "error")
        LLM_REQUESTS.labels(model=model, result=result).inc()
        if result not in ("disabled", "error"):
            LLM_LATENCY.labels(model=model).observe(duration)


@contextmanager
def track_keyphrases_call() -> Generator[dict, None, None]:
    """Track KeyBERT extraction timing and result.

    Usage:
        with track_keyphrases_call() as ctx:
            phrases = extract_keyphrases(text)
            ctx["result"] = "success"  # or "cache_hit"
    """
    start = time.time()
    context = {"result": "error"}

    try:
        yield context
    finally:
        duration = time.time() - start
        result = context.get("result", "error")
        KEYPHRASES_REQUESTS.labels(result=result).inc()
        if result != "cache_hit":
            KEYPHRASES_LATENCY.observe(duration)


def track_scan_stage(endpoint: str, stage: str, duration_seconds: float):
    """Record duration for a specific scan pipeline stage.

    Args:
        endpoint: API endpoint (e.g., "/api/v1/scan")
        stage: Pipeline stage (html_fetch, psi, keyphrases, ai, rules)
        duration_seconds: Stage duration in seconds
    """
    SCAN_DURATION.labels(endpoint=endpoint, stage=stage).observe(duration_seconds)


def track_scan_error(error_type: str):
    """Increment scan error counter.

    Args:
        error_type: Error classification (ssrf, timeout, http_error, parse_error, llm_error)
    """
    SCAN_ERRORS.labels(error_type=error_type).inc()


def track_background_job(job_type: str, result: str, duration_seconds: float | None = None):
    """Track background job execution.

    Args:
        job_type: Job type (e.g., "scan_job", "cleanup")
        result: Job result (enqueued, started, completed, failed)
        duration_seconds: Job duration (only for completed/failed)
    """
    BACKGROUND_JOBS_TOTAL.labels(job_type=job_type, result=result).inc()
    if duration_seconds is not None and result in ("completed", "failed"):
        BACKGROUND_JOB_DURATION.labels(job_type=job_type).observe(duration_seconds)


def update_queue_size(queue_name: str, size: int):
    """Update job queue size gauge.

    Args:
        queue_name: Queue identifier
        size: Current queue depth
    """
    JOB_QUEUE_SIZE.labels(queue_name=queue_name).set(size)


def track_cache_request(cache_type: str, hit: bool):
    """Track cache hit/miss.

    Args:
        cache_type: Cache category (psi, keyphrases, lighthouse)
        hit: True for cache hit, False for miss
    """
    result = "hit" if hit else "miss"
    CACHE_REQUESTS.labels(cache_type=cache_type, result=result).inc()


def track_premium_conversion(source: str = "stripe"):
    """Track premium upgrade event.

    Args:
        source: Conversion source (stripe, manual)
    """
    PREMIUM_CONVERSIONS.labels(source=source).inc()


def update_active_scan_jobs(status_counts: dict[str, int]):
    """Update active scan jobs gauge by status.

    Args:
        status_counts: Dict mapping status to count (e.g., {"RUNNING": 3, "QUEUED": 5})
    """
    for status, count in status_counts.items():
        SCAN_JOBS_ACTIVE.labels(status=status).set(count)

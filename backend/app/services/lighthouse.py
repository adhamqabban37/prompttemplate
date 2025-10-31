"""Lighthouse (PageSpeed Insights) helper.

This module calls the Google PageSpeed Insights API (free tier) to fetch
performance and SEO metrics for a given URL. It retries transient failures
using tenacity and returns a normalized dict with key metrics and a small
raw subset for debugging.

Features:
- Caching: Results cached for PSI_CACHE_TTL_SECONDS (default 12h)
- Deduplication: In-flight requests for same URL return same result
- Circuit breaker: Auto-disable PSI for 5min after 3 consecutive failures

Env:
  PSI_API_KEY - Google Pagespeed API key (required for full functionality)
  PSI_CACHE_TTL_SECONDS - Cache TTL in seconds (default 43200 = 12h)
"""
from __future__ import annotations

import os
import requests
import time
import threading
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
from typing import Any, Dict, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache structure: {(url, strategy): (result_dict, timestamp)}
_psi_cache: Dict[tuple, tuple[Dict[str, Any], float]] = {}
_cache_lock = threading.Lock()

# Deduplication: track in-flight requests
_in_flight: Dict[str, threading.Event] = {}
_in_flight_results: Dict[str, Dict[str, Any]] = {}
_in_flight_lock = threading.Lock()

# Circuit breaker state
_circuit_breaker_failures = 0
_circuit_breaker_tripped_until = 0.0
_circuit_breaker_lock = threading.Lock()
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_RESET_SECONDS = 300  # 5 minutes


def _parse_score(field: Any) -> Optional[int]:
    try:
        if field is None:
            return None
        # PSI returns 0..1 for performance in some places; convert to 0..100
        if isinstance(field, (int, float)):
            val = float(field)
            if 0 <= val <= 1:
                return int(round(val * 100))
            return int(round(val))
        return None
    except Exception:
        return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10),
       retry=retry_if_exception_type((requests.exceptions.RequestException,)))
def _call_psi(url: str, key: str, timeout: int = 12) -> Dict[str, Any]:
    endpoint = (
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    )
    params = {
        "url": url,
        "category": ["PERFORMANCE", "SEO"],
        "strategy": "mobile",
        "key": key,
    }
    # requests will serialise list params correctly
    resp = requests.get(endpoint, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_psi(url: str, strategy: str = "mobile") -> Dict[str, Any]:
    """Fetch PSI data for a URL and normalize some important fields.
    
    Includes caching, deduplication, and circuit breaker.

    Returns a dict with keys: source, available(bool), performance, seo,
    web_vitals (lcp_ms, inp_ms, cls, tbt_ms), raw (small debug dict)
    """
    key = os.getenv("PSI_API_KEY")
    if not key:
        logger.info("PSI_API_KEY not set - skipping PageSpeed Insights")
        return {"source": "psi", "available": False, "reason": "no_api_key"}
    
    # Check circuit breaker
    global _circuit_breaker_failures, _circuit_breaker_tripped_until
    with _circuit_breaker_lock:
        if _circuit_breaker_tripped_until > time.time():
            remaining = int(_circuit_breaker_tripped_until - time.time())
            logger.warning(f"PSI circuit breaker tripped, {remaining}s remaining")
            return {
                "source": "psi",
                "available": False,
                "reason": "circuit_breaker",
                "retry_after_seconds": remaining
            }
    
    cache_key = (url, strategy)
    cache_ttl = settings.PSI_CACHE_TTL_SECONDS
    
    # Check cache
    with _cache_lock:
        if cache_key in _psi_cache:
            cached_result, cached_time = _psi_cache[cache_key]
            age = time.time() - cached_time
            if age < cache_ttl:
                logger.info(f"PSI cache hit for {url} (age={int(age)}s)")
                return cached_result
            else:
                # Expired, remove
                del _psi_cache[cache_key]
    
    # Check if request already in flight
    with _in_flight_lock:
        if url in _in_flight:
            logger.info(f"PSI request for {url} already in flight, waiting...")
            event = _in_flight[url]
        else:
            # Mark as in-flight
            event = threading.Event()
            _in_flight[url] = event
    
    # If we're waiting on another request
    if url in _in_flight_results:
        event.wait(timeout=30)
        with _in_flight_lock:
            if url in _in_flight_results:
                result = _in_flight_results[url]
                del _in_flight_results[url]
                return result
    
    # We're the primary request, do the fetch
    try:
        psi_timeout = int(os.getenv("PSI_TIMEOUT_SECONDS", "12"))
        data = _call_psi(url, key, timeout=psi_timeout)
        
        # Reset circuit breaker on success
        with _circuit_breaker_lock:
            _circuit_breaker_failures = 0
        
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else 0
        logger.error(f"PSI HTTP error for {url}: status={status}")
        
        # Trip circuit breaker on repeated failures
        with _circuit_breaker_lock:
            _circuit_breaker_failures += 1
            if _circuit_breaker_failures >= CIRCUIT_BREAKER_THRESHOLD:
                _circuit_breaker_tripped_until = time.time() + CIRCUIT_BREAKER_RESET_SECONDS
                logger.error(f"PSI circuit breaker TRIPPED after {_circuit_breaker_failures} failures")
        
        result = {"source": "psi", "available": False, "error": str(e), "status_code": status}
        _store_and_notify(url, cache_key, result, event)
        return result
        
    except Exception as e:
        logger.warning(f"PSI request failed for {url}: {type(e).__name__}: {e}")
        result = {"source": "psi", "available": False, "error": str(e)}
        _store_and_notify(url, cache_key, result, event)
        return result

    # Navigate the response safely
    lighthouse = data.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})

    perf_score = _parse_score(categories.get("performance", {}).get("score"))
    seo_score = _parse_score(categories.get("seo", {}).get("score"))

    # Web Vitals best-effort extraction
    def _ms(audit_name: str) -> Optional[int]:
        val = audits.get(audit_name, {}).get("numericValue")
        try:
            return int(round(float(val))) if val is not None else None
        except Exception:
            return None

    lcp_ms = _ms("largest-contentful-paint")
    inp_ms = _ms("experimental-interaction-to-next-paint") or _ms("interaction-to-next-paint")
    cls = None
    try:
        cls_val = audits.get("cumulative-layout-shift", {}).get("numericValue")
        cls = float(cls_val) if cls_val is not None else None
    except Exception:
        cls = None

    tbt_ms = _ms("total-blocking-time")

    result = {
        "source": "psi",
        "available": True,
        "performance": perf_score,
        "seo": seo_score,
        "web_vitals": {
            "lcp_ms": lcp_ms,
            "inp_ms": inp_ms,
            "cls": cls,
            "tbt_ms": tbt_ms,
        },
        "raw": {
            "requestedUrl": data.get("id"),
            "lighthouseVersion": lighthouse.get("lighthouseVersion"),
            "fetchTime": lighthouse.get("fetchTime"),
        },
    }
    
    _store_and_notify(url, cache_key, result, event)
    return result


def _store_and_notify(url: str, cache_key: tuple, result: Dict[str, Any], event: threading.Event) -> None:
    """Store result in cache and notify waiting threads."""
    # Cache the result
    with _cache_lock:
        _psi_cache[cache_key] = (result, time.time())
    
    # Notify waiting threads
    with _in_flight_lock:
        _in_flight_results[url] = result
        if url in _in_flight:
            del _in_flight[url]
    event.set()

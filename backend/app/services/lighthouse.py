"""Lighthouse (PageSpeed Insights) helper.

This module calls the Google PageSpeed Insights API (free tier) to fetch
performance and SEO metrics for a given URL. It retries transient failures
using tenacity and returns a normalized dict with key metrics and a small
raw subset for debugging.

Env:
  PSI_API_KEY - Google Pagespeed API key (required for full functionality)

Notes:
  - PSI may be rate limited; keep requests light and cache results if used at scale.
  - If PSI_API_KEY is not set, fetch_psi returns {'source':'psi','available':False}
"""
from __future__ import annotations

import os
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


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
def _call_psi(url: str, key: str, timeout: int = 30) -> Dict[str, Any]:
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


def fetch_psi(url: str) -> Dict[str, Any]:
    """Fetch PSI data for a URL and normalize some important fields.

    Returns a dict with keys: source, available(bool), performance, seo,
    web_vitals (lcp_ms, inp_ms, cls, tbt_ms), raw (small debug dict)
    """
    key = os.getenv("PSI_API_KEY")
    if not key:
        logger.info("PSI_API_KEY not set - skipping PageSpeed Insights")
        return {"source": "psi", "available": False}

    try:
        data = _call_psi(url, key)
    except Exception as e:
        logger.warning(f"PSI request failed for {url}: {e}")
        return {"source": "psi", "available": False, "error": str(e)}

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
    # INP may be experimental, try known keys
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

    return result

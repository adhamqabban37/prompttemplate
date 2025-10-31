from __future__ import annotations

import os
import time
import json
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import uuid

import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import logging
from app.services.lighthouse import fetch_psi
from app.services.crewai_reasoner import generate_recommendations
from app.services.rules_loader import get_rules
from app.services.check_engine import evaluate_rules
from app.utils.url_validator import validate_url_or_raise, SSRFProtectionError
from app.services.keyphrases import extract_keyphrases
from app.services.fetcher import fetch_html, extract_title as bs_extract_title
from app.metrics import (
    track_scan_request,
    track_scan_stage,
    track_scan_error,
    SCAN_REQUESTS_TOTAL,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scan", tags=["scan"]) 

# Basic concurrency and rate limiting
import asyncio
_scan_semaphore = asyncio.Semaphore(int(os.getenv("SCAN_MAX_CONCURRENCY", "3")))
_rate_window_seconds = 60
_rate_limit_per_min = int(os.getenv("SCAN_RATE_LIMIT_PER_MIN", "30"))
_rate_counters: dict[str, list[float]] = {}
_rate_lock = asyncio.Lock()


class ScanRequest(BaseModel):
    url: str


class MetadataSummary(BaseModel):
    json_ld_count: int = 0
    microdata_count: int = 0
    opengraph_count: int = 0


class ScanResponse(BaseModel):
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    text_preview: Optional[str] = None
    schemas: List[Dict[str, Any]] = []
    metadata_summary: MetadataSummary
    keyphrases: List[str] = []
    error: Optional[str] = None
    # New optional fields populated by Lighthouse + CrewAI
    lighthouse: Optional[Dict[str, Any]] = None
    visibility: Optional[Dict[str, Any]] = None
    insights: Optional[Dict[str, Any]] = None
    timings: Optional[Dict[str, int]] = None


@router.get("/", response_model=ScanResponse)
def scan_url_get(url: str, request: Request) -> ScanResponse:
    """GET variant for scanning, to support `?url=` usage."""
    return scan_url(ScanRequest(url=url), request)


def extract_local(url: str) -> ScanResponse:
    """
    Download HTML and extract metadata using requests + trafilatura + extruct.
    Returns proper error messages for timeout, SSL, DNS, and HTTP errors.
    """
    try:
        import trafilatura
        import extruct
        from w3lib.html import get_base_url
    except ImportError as e:
        logger.error(f"Missing library: {e}")
        return ScanResponse(
            url=url,
            error=f"Server configuration error: Missing library {e}",
            metadata_summary=MetadataSummary(),
        )

    # Fetch HTML with async httpx client (timed)
    try:
        import anyio
        timeout_s = int(os.getenv("EXTRACT_TIMEOUT_SECONDS", "20"))
        html, html_ms = anyio.run(fetch_html, url, timeout_s)
    except Exception as e:
        emsg = str(e)
        if "timed out" in emsg.lower():
            detail = "Request timeout - website took too long to respond"
        elif "ssl" in emsg.lower():
            detail = "SSL certificate error - website may have invalid HTTPS configuration"
        elif "name or service not known" in emsg.lower() or "temporary failure in name resolution" in emsg.lower():
            detail = "DNS resolution failed - check domain"
        elif "connecterror" in type(e).__name__.lower() or "connection" in emsg.lower():
            detail = "Connection error - website may be down or DNS failed"
        else:
            detail = f"Unexpected error: {emsg}"
        logger.warning(json.dumps({"event": "html_fetch_failed", "url": url, "error": emsg}))
        return ScanResponse(url=url, error=detail, metadata_summary=MetadataSummary())

    # Title via BeautifulSoup (with meta/h1/hostname fallbacks)
    title = bs_extract_title(html, url)
    base_url = get_base_url(html, url)

    try:
        # Extract readable text
        try:
            text = trafilatura.extract(html, output_format="txt", include_comments=False) or ""
            text_preview = text[:500] if text else None
        except Exception as e:
            import traceback
            logger.error(f"Trafilatura error for {url}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            text = ""
            text_preview = None

        # KeyBERT keyphrases (timed)
        keyphrases: List[str] = []
        keyphrases_ms: int = 0
        try:
            kp_start = time.time()
            top_n = int(os.getenv("KEYPHRASES_TOP_N", "8"))
            timeout_ms = int(os.getenv("KEYPHRASES_TIMEOUT_MS", "2000"))
            keyphrases = extract_keyphrases(text or "", top_n=top_n, timeout_ms=timeout_ms, cache_key=url)
            keyphrases_ms = int((time.time() - kp_start) * 1000)
        except Exception as e:
            keyphrases_ms = int((time.time() - kp_start) * 1000)
            logger.warning(json.dumps({"event":"keyphrases_failed","url":url,"error":str(e),"duration_ms": keyphrases_ms}))

        # Extract metadata (defensive against library return shape changes)
        try:
            metadata = extruct.extract(
                html,
                base_url=base_url,
                syntaxes=["json-ld", "microdata", "opengraph"],
            )
        except Exception as e:
            logger.warning(json.dumps({
                "event": "extruct_failed",
                "url": url,
                "error": str(e),
            }))
            metadata = {}

        if not isinstance(metadata, dict):
            logger.warning(json.dumps({
                "event": "extruct_unexpected_shape",
                "url": url,
                "type": str(type(metadata)),
            }))
            metadata = {}

        # Build schemas list and counts
        schemas: List[Dict[str, Any]] = []
        json_ld_items = metadata.get("json-ld", []) if isinstance(metadata, dict) else []
        microdata_items = metadata.get("microdata", []) if isinstance(metadata, dict) else []
        opengraph_items = metadata.get("opengraph", []) if isinstance(metadata, dict) else []

        # Normalize potential unexpected shapes to lists
        if not isinstance(json_ld_items, list):
            json_ld_items = []
        if not isinstance(microdata_items, list):
            microdata_items = []
        if not isinstance(opengraph_items, list):
            opengraph_items = []

        for item in json_ld_items:
            schemas.append({"type": "json-ld", "data": item})
        for item in microdata_items:
            schemas.append({"type": "microdata", "data": item})
        for item in opengraph_items:
            schemas.append({"type": "opengraph", "data": item})

        summary = MetadataSummary(
            json_ld_count=len(json_ld_items),
            microdata_count=len(microdata_items),
            opengraph_count=len(opengraph_items),
        )

        # Extract title and description from OpenGraph if available (only if not already found)
        if not title:
            title = None
        description = None
        for og in opengraph_items:
            # extruct typically returns objects with a 'properties' dict mapping keys to lists
            if not isinstance(og, dict):
                continue  # Skip non-dict items
            
            # Safely get properties if it exists and is a dict
            props_raw = og.get("properties")
            props = props_raw if isinstance(props_raw, dict) else {}
            
            # Try direct keys first
            if not title:
                candidate = og.get("og:title")
                if isinstance(candidate, list):
                    candidate = candidate[0] if candidate else None
                if not candidate and props:
                    candidate = props.get("og:title")
                    if isinstance(candidate, list):
                        candidate = candidate[0] if candidate else None
                if isinstance(candidate, str) and candidate.strip():
                    title = candidate.strip()
            if not description:
                candidate = og.get("og:description")
                if isinstance(candidate, list):
                    candidate = candidate[0] if candidate else None
                if not candidate and props:
                    candidate = props.get("og:description")
                    if isinstance(candidate, list):
                        candidate = candidate[0] if candidate else None
                if isinstance(candidate, str) and candidate.strip():
                    description = candidate.strip()

        # Final fallback already attempted via BeautifulSoup earlier

        response = ScanResponse(
            url=url,
            title=title,
            description=description,
            text_preview=text_preview,
            schemas=schemas,
            metadata_summary=summary,
            keyphrases=keyphrases,
        )
        # Attach granular timings so frontend can show HTML/Keyphrases separately
        try:
            # html_ms defined during fetch; keyphrases_ms measured above
            response.timings = {"html_ms": html_ms, "keyphrases_ms": keyphrases_ms}
        except Exception:
            pass
        return response
    except Exception as e:
        import traceback
        logger.error(f"Error extracting metadata from {url}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ScanResponse(
            url=url,
            error=f"Extraction error: {str(e)}",
            metadata_summary=MetadataSummary(),
        )


def extract_firecrawl(url: str) -> ScanResponse:
    """
    Use Firecrawl API to scrape and extract metadata (optional fallback).
    """
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        logger.warning("FIRECRAWL_API_KEY not set")
        return ScanResponse(
            url=url,
            error="Firecrawl API key not configured",
            metadata_summary=MetadataSummary(),
        )

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"url": url, "formats": ["markdown", "html", "extract"]}

    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        return ScanResponse(
            url=url,
            title=data.get("metadata", {}).get("title"),
            description=data.get("metadata", {}).get("description"),
            text_preview=data.get("markdown", "")[:500] if data.get("markdown") else None,
            schemas=[],
            metadata_summary=MetadataSummary(),
        )
    except Exception as e:
        logger.error(f"Firecrawl API error: {e}")
        return ScanResponse(
            url=url,
            error=f"Firecrawl API error: {str(e)}",
            metadata_summary=MetadataSummary(),
        )


async def _rate_check(ip: str) -> bool:
    now = time.time()
    cutoff = now - _rate_window_seconds
    async with _rate_lock:
        hist = _rate_counters.get(ip, [])
        hist = [t for t in hist if t >= cutoff]
        if len(hist) >= _rate_limit_per_min:
            _rate_counters[ip] = hist
            return False
        hist.append(now)
        _rate_counters[ip] = hist
        return True


@router.post("/", response_model=ScanResponse)
def scan_url(payload: ScanRequest, request: Request) -> ScanResponse:
    """
    Scan a URL and extract metadata.
    Uses local extraction (trafilatura + extruct) by default.
    Falls back to Firecrawl API if FIRECRAWL_API_KEY is set.
    """
    # Generate scan ID for observability
    scan_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    url = payload.url.strip()
    # Enforce request size/URL length limits
    if len(url) > 2048:
        raise HTTPException(status_code=400, detail="URL too long (max 2048 characters)")

    client_ip = request.client.host if request.client else "unknown"

    # Structured logging: scan start
    logger.info(json.dumps({
        "event": "scan_start",
        "scan_id": scan_id,
        "url": url,
        "timestamp": time.time(),
    }))
    
    # Track scan request with metrics
    with track_scan_request("/api/v1/scan") as metrics_ctx:
        # Rate limit per-IP
        try:
            import anyio
            # Run async rate-check in a blocking context
            ok = anyio.run(_rate_check, client_ip)
        except Exception:
            ok = True
        if not ok:
            raise HTTPException(status_code=429, detail="Rate limit exceeded, try again later")

        # SSRF protection: validate URL before any network requests
        try:
            validate_url_or_raise(url)
        except SSRFProtectionError as e:
            logger.warning(json.dumps({
                "event": "scan_rejected",
                "scan_id": scan_id,
                "url": url,
                "reason": "ssrf_protection",
                "error": str(e),
            }))
            track_scan_error("ssrf")
            # Enforce HTTP 400 for SSRF attempts
            raise HTTPException(status_code=400, detail=f"URL rejected: {str(e)}")

        # Validate URL format (redundant after SSRF check, but kept for clarity)
        if not url.startswith(("http://", "https://")):
            logger.warning(json.dumps({
                "event": "scan_rejected",
                "scan_id": scan_id,
                "url": url,
                "reason": "invalid_scheme",
            }))
            return ScanResponse(
                url=url,
                error="Invalid URL - must start with http:// or https://",
                metadata_summary=MetadataSummary(),
            )

        # Step 1: Extract metadata
        extract_start = time.time()
        result = extract_local(url)
        extract_ms = int((time.time() - extract_start) * 1000)
    
    logger.info(json.dumps({
        "event": "extract_complete",
        "scan_id": scan_id,
        "url": url,
        "duration_ms": extract_ms,
        "has_error": bool(result.error),
    }))

    # If local extraction failed and Firecrawl is configured, try it
    if result.error and os.getenv("FIRECRAWL_API_KEY"):
        logger.info(f"Local extraction failed for {url}, trying Firecrawl...")
        firecrawl_start = time.time()
        result = extract_firecrawl(url)
        firecrawl_ms = int((time.time() - firecrawl_start) * 1000)
        logger.info(json.dumps({
            "event": "firecrawl_complete",
            "scan_id": scan_id,
            "url": url,
            "duration_ms": firecrawl_ms,
        }))

    # Convert ScanResponse -> dict for augmentation
    scan_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

    # Step 2: Fetch Lighthouse (PSI) results
    psi_start = time.time()
    try:
        lighthouse = fetch_psi(url)
        psi_ms = int((time.time() - psi_start) * 1000)
        logger.info(json.dumps({
            "event": "psi_complete",
            "scan_id": scan_id,
            "url": url,
            "duration_ms": psi_ms,
            "available": lighthouse.get("available", False),
        }))
    except Exception as e:
        psi_ms = int((time.time() - psi_start) * 1000)
        logger.warning(json.dumps({
            "event": "psi_failed",
            "scan_id": scan_id,
            "url": url,
            "duration_ms": psi_ms,
            "error": str(e),
        }))
        lighthouse = {"source": "psi", "available": False, "error": str(e)}

    # Prepare lightweight scan payload subset for CrewAI
    scan_payload_subset = {
        "url": url,
        "title": scan_dict.get("title"),
        "description": scan_dict.get("description"),
        "text_preview": scan_dict.get("text_preview"),
        "schemas": scan_dict.get("schemas", []),
        "metadata_summary": scan_dict.get("metadata_summary", {}),
        "keyphrases": scan_dict.get("keyphrases", []),
    }

    # Step 3: Generate AI insights
    insights_start = time.time()
    if result.error:
        insights = {
            "visibility_score_explainer": "AI insights unavailable due to extraction error.",
            "top_findings": [],
            "recommendations": [],
        }
        insights_ms = 0
    else:
        # Generate AI insights with timeout and safe fallback
        if os.getenv("DISABLE_AI", "0") == "1":
            logger.info(json.dumps({
                "event": "ai_disabled",
                "scan_id": scan_id,
                "reason": "DISABLE_AI=1",
            }))
            insights = {
                "visibility_score_explainer": "Visibility score based on technical signals. AI disabled.",
                "top_findings": ["AI analysis disabled - showing rule-based results only"],
                "recommendations": [],
            }
            insights_ms = 0
        else:
            try:
                def _run_gen() -> Dict[str, Any]:
                    return generate_recommendations(scan_payload_subset, lighthouse, timeout_seconds=15)

                with ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(_run_gen)
                    insights = fut.result(timeout=20)  # slightly above internal LLM timeout
                insights_ms = int((time.time() - insights_start) * 1000)
                logger.info(json.dumps({
                    "event": "ai_complete",
                    "scan_id": scan_id,
                    "url": url,
                    "duration_ms": insights_ms,
                }))
            except FuturesTimeoutError as e:
                insights_ms = int((time.time() - insights_start) * 1000)
                logger.warning(json.dumps({
                    "event": "ai_timeout",
                    "scan_id": scan_id,
                    "url": url,
                    "duration_ms": insights_ms,
                }))
                insights = {
                    "visibility_score_explainer": "Visibility score based on technical signals. AI insights timed out.",
                    "top_findings": ["AI analysis temporarily unavailable - showing rule-based results only"],
                    "recommendations": [],
                }
            except Exception as e:
                insights_ms = int((time.time() - insights_start) * 1000)
                logger.warning(json.dumps({
                    "event": "ai_failed",
                    "scan_id": scan_id,
                    "url": url,
                    "duration_ms": insights_ms,
                    "error": str(e),
                }))
                insights = {
                    "visibility_score_explainer": "Visibility score based on technical signals. AI insights unavailable.",
                    "top_findings": ["AI analysis temporarily unavailable - showing rule-based results only"],
                    "recommendations": [],
                }

    # Compute a simple visibility score and signals
    signals: List[str] = []
    score = 50
    perf = lighthouse.get("performance") if isinstance(lighthouse, dict) else None
    seo = lighthouse.get("seo") if isinstance(lighthouse, dict) else None
    webv = lighthouse.get("web_vitals", {}) if isinstance(lighthouse, dict) else {}

    if perf is not None and perf >= 75:
        score += 10
        signals.append("Good performance")
    if seo is not None and seo >= 80:
        score += 10
        signals.append("Good SEO")
    # LocalBusiness / FAQ schema checks
    # Coerce metadata_summary to dict for safe access
    _ms = scan_payload_subset.get("metadata_summary") or {}
    if hasattr(_ms, "model_dump"):
        md = _ms.model_dump()
    elif hasattr(_ms, "dict"):
        md = _ms.dict()
    elif isinstance(_ms, dict):
        md = _ms
    else:
        md = {}
    if md.get("json_ld_count", 0) > 0:
        # look for LocalBusiness/FAQ in schemas
        schemas = scan_payload_subset.get("schemas", [])
        found_local = any("LocalBusiness" in str(s.get("data", "")) for s in schemas)
        found_faq = any("FAQPage" in str(s.get("data", "")) or "Question" in str(s.get("data", "")) for s in schemas)
        if found_local:
            score += 10
            signals.append("LocalBusiness schema present")
        if found_faq:
            score += 10
            signals.append("FAQ schema present")

    lcp = webv.get("lcp_ms")
    if lcp is not None and lcp < 2500:
        score += 10
        signals.append("Good LCP")

    # Cap score
    if score > 100:
        score = 100
    if score < 0:
        score = 0

    visibility = {"score": score, "signals": signals}

    # Attach augmented fields to response
    result.lighthouse = lighthouse
    result.visibility = visibility
    result.insights = insights
    # Merge granular timings (html_ms, keyphrases_ms) if set earlier
    _timings_existing = result.timings or {}
    _timings_existing.update({
        "extract_ms": extract_ms,
        "psi_ms": psi_ms,
        "insights_ms": insights_ms,
        "total_ms": int((time.time() - start_time) * 1000),
    })
    result.timings = _timings_existing

    # Rules engine: evaluate YAML-driven checks and merge
    try:
        rules, last_mtime = get_rules()
        eval_out = evaluate_rules({"scan": scan_dict, "lighthouse": lighthouse}, rules)

        # Merge signals (dedup)
        rule_signals = eval_out.get("signals", [])
        if isinstance(result.visibility, dict):
            existing = set(result.visibility.get("signals", []))
            merged = list(existing.union(rule_signals))
            result.visibility["signals"] = merged

        # Adjust score with clamp (-30..+30) and cap 0..100
        delta = int(eval_out.get("score_delta", 0))
        if delta > 30:
            delta = 30
        if delta < -30:
            delta = -30
        if isinstance(result.visibility, dict):
            new_score = int(result.visibility.get("score", 0)) + delta
            if new_score > 100:
                new_score = 100
            if new_score < 0:
                new_score = 0
            result.visibility["score"] = new_score

        # Merge recommendations
        rule_recs = eval_out.get("recommendations", [])
        if not isinstance(result.insights, dict):
            result.insights = {}
        rec_list = result.insights.get("recommendations", []) if isinstance(result.insights, dict) else []
        # Deduplicate by rule_id+title
        seen = {f"{r.get('rule_id')}::{r.get('title')}" for r in rec_list if isinstance(r, dict)}
        for r in rule_recs:
            key = f"{r.get('rule_id')}::{r.get('title')}"
            if key not in seen:
                rec_list.append(r)
                seen.add(key)
        if isinstance(result.insights, dict):
            result.insights["recommendations"] = rec_list
    except Exception as e:
        # Non-fatal: keep response usable even if rules fail
        logger.warning(f"Rules evaluation failed: {e}")
    
        # Final structured logging with total scan time
        total_ms = int((time.time() - start_time) * 1000)
        logger.info(json.dumps({
            "event": "scan_complete",
            "scan_id": scan_id,
            "url": url,
            "extract_ms": extract_ms,
            "psi_ms": psi_ms,
            "insights_ms": insights_ms,
            "total_ms": total_ms,
            "has_error": bool(result.error),
        }))
        
        # Track metrics for each stage
        track_scan_stage("/api/v1/scan", "html_fetch", extract_ms / 1000.0)
        track_scan_stage("/api/v1/scan", "psi", psi_ms / 1000.0)
        track_scan_stage("/api/v1/scan", "ai", insights_ms / 1000.0)
        
        # Mark scan as successful if no errors
        if not result.error:
            metrics_ctx["result"] = "success"
        
        return result

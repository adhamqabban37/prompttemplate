from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from app.services.lighthouse import fetch_psi
from app.services.crewai_reasoner import generate_recommendations
from app.services.rules_loader import get_rules
from app.services.check_engine import evaluate_rules

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scan", tags=["scan"])


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
    error: Optional[str] = None
    # New optional fields populated by Lighthouse + CrewAI
    lighthouse: Optional[Dict[str, Any]] = None
    visibility: Optional[Dict[str, Any]] = None
    insights: Optional[Dict[str, Any]] = None


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

    # Robust request headers to avoid bot blocking
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 XenlixAI/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        resp = requests.get(
            url,
            headers=headers,
            timeout=15,  # Increased timeout
            allow_redirects=True,
            verify=True,  # SSL verification enabled
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching {url}")
        return ScanResponse(
            url=url,
            error="Request timeout - website took too long to respond",
            metadata_summary=MetadataSummary(),
        )
    except requests.exceptions.SSLError as e:
        logger.warning(f"SSL error fetching {url}: {e}")
        return ScanResponse(
            url=url,
            error="SSL certificate error - website may have invalid HTTPS configuration",
            metadata_summary=MetadataSummary(),
        )
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"Connection error fetching {url}: {e}")
        return ScanResponse(
            url=url,
            error="Connection error - website may be down or DNS failed",
            metadata_summary=MetadataSummary(),
        )
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP error fetching {url}: {e}")
        status_code = e.response.status_code if e.response else 0
        if status_code == 403:
            return ScanResponse(
                url=url,
                error="Access forbidden (403) - website blocked our scan request",
                metadata_summary=MetadataSummary(),
            )
        elif status_code == 404:
            return ScanResponse(
                url=url,
                error="Page not found (404) - URL does not exist",
                metadata_summary=MetadataSummary(),
            )
        else:
            return ScanResponse(
                url=url,
                error=f"HTTP error {status_code} - website returned an error",
                metadata_summary=MetadataSummary(),
            )
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        return ScanResponse(
            url=url,
            error=f"Unexpected error: {str(e)}",
            metadata_summary=MetadataSummary(),
        )

    html = resp.text
    base_url = get_base_url(html, url)

    try:
        # Extract readable text
        text = trafilatura.extract(html, output_format="txt", include_comments=False) or ""
        text_preview = text[:500] if text else None

        # Extract metadata
        metadata = extruct.extract(
            html,
            base_url=base_url,
            syntaxes=["json-ld", "microdata", "opengraph"],
        )

        # Build schemas list and counts
        schemas: List[Dict[str, Any]] = []
        json_ld_items = metadata.get("json-ld", [])
        microdata_items = metadata.get("microdata", [])
        opengraph_items = metadata.get("opengraph", [])

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

        # Extract title and description from OpenGraph if available
        title = None
        description = None
        for og in opengraph_items:
            if not title:
                # Handle both dict and list formats for OG properties
                if isinstance(og, dict):
                    title = og.get("og:title") or og.get("properties", {}).get("og:title")
                    if isinstance(title, list) and title:
                        title = title[0]
            if not description:
                if isinstance(og, dict):
                    description = og.get("og:description") or og.get("properties", {}).get("og:description")
                    if isinstance(description, list) and description:
                        description = description[0]

        # Fallback: extract title from HTML
        if not title:
            import re
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            if title_match:
                title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()

        return ScanResponse(
            url=url,
            title=title,
            description=description,
            text_preview=text_preview,
            schemas=schemas,
            metadata_summary=summary,
        )
    except Exception as e:
        logger.error(f"Error extracting metadata from {url}: {e}")
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


@router.post("/", response_model=ScanResponse)
def scan_url(payload: ScanRequest) -> ScanResponse:
    """
    Scan a URL and extract metadata.
    Uses local extraction (trafilatura + extruct) by default.
    Falls back to Firecrawl API if FIRECRAWL_API_KEY is set.
    """
    url = payload.url.strip()

    # Validate URL format
    if not url.startswith(("http://", "https://")):
        return ScanResponse(
            url=url,
            error="Invalid URL - must start with http:// or https://",
            metadata_summary=MetadataSummary(),
        )

    # Try local extraction first
    result = extract_local(url)

    # If local extraction failed and Firecrawl is configured, try it
    if result.error and os.getenv("FIRECRAWL_API_KEY"):
        logger.info(f"Local extraction failed for {url}, trying Firecrawl...")
        result = extract_firecrawl(url)

    # Convert ScanResponse -> dict for augmentation
    scan_dict = result.model_dump() if hasattr(result, "model_dump") else result.__dict__

    # Fetch Lighthouse (PSI) results (may return available=False)
    try:
        lighthouse = fetch_psi(url)
    except Exception as e:
        logger.warning(f"Lighthouse fetch failed: {e}")
        lighthouse = {"source": "psi", "available": False, "error": str(e)}

    # Prepare lightweight scan payload subset for CrewAI
    scan_payload_subset = {
        "url": url,
        "title": scan_dict.get("title"),
        "description": scan_dict.get("description"),
        "text_preview": scan_dict.get("text_preview"),
        "schemas": scan_dict.get("schemas", []),
        "metadata_summary": scan_dict.get("metadata_summary", {}),
    }

    # Generate insights only if extraction succeeded; otherwise return a friendly placeholder
    if result.error:
        insights = {
            "visibility_score_explainer": "AI insights unavailable due to extraction error.",
            "top_findings": [],
            "recommendations": [],
        }
    else:
        insights = generate_recommendations(scan_payload_subset, lighthouse)

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

    return result

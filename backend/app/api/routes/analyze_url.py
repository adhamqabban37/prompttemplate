from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.utils.url_validator import validate_url_or_raise, SSRFProtectionError
from app.services.fetcher import fetch_html, parse_html_summary
from app.services.lighthouse import fetch_psi
from app.services.keyphrases import extract_keyphrases

# Reuse internal helpers from orchestrator for scoring and business extraction
from app.api.routes.orchestrator import _compute_scores, _extract_structured_data_summary, _extract_business_entity


router = APIRouter(tags=["analyze-url"])  # no prefix; endpoint path defined explicitly below


class AnalyzeUrlRequest(BaseModel):
    url: str
    free_test_mode: bool = True


class AnalyzeUrlResponse(BaseModel):
    target_url: str
    status: str
    page_title: Optional[str]
    meta_description: Optional[str]
    final_url: str
    http_status: Optional[int]
    headings: Dict[str, List[str]]
    structured_data_summary: Dict[str, Any]
    schema_blocks: List[Dict[str, Any]]
    nap: Dict[str, Optional[str]]
    keyphrases: List[Dict[str, Any]]
    psi_snapshot: Dict[str, Any]
    aeo_score: int
    geo_score: int
    aeo_dimensions: List[Dict[str, Any]]
    geo_dimensions: List[Dict[str, Any]]
    weaknesses: List[Dict[str, Any]]
    recommendations: List[str]
    checkout: Dict[str, Any]
    premium_preview: bool
    timings: Dict[str, int] = Field(default_factory=dict)


@router.post("/analyze-url", response_model=AnalyzeUrlResponse)
def analyze_url(payload: AnalyzeUrlRequest) -> AnalyzeUrlResponse:
    start = time.time()
    url = payload.url.strip()

    # SSRF guard and URL validation
    try:
        validate_url_or_raise(url)
    except SSRFProtectionError as e:
        raise HTTPException(status_code=400, detail=f"URL rejected: {e}")

    # Resolve final URL + status with a quick HEAD/GET
    final_url = url
    http_status: Optional[int] = None
    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            r = client.get(url)
            final_url = str(r.url)
            http_status = r.status_code
    except Exception:
        # Non-fatal; continue with original URL
        pass

    # Fetch HTML (async function bridged via anyio)
    html: str = ""
    html_ms = 0
    try:
        import anyio
        timeout_s = int(os.getenv("EXTRACT_TIMEOUT_SECONDS", "20"))
        html, html_ms = anyio.run(fetch_html, final_url, timeout_s)
    except Exception:
        # Continue with empty HTML to keep response consistent
        html = ""

    # Parse HTML summary (never throws)
    summary = parse_html_summary(html, final_url)

    # Structured data summary & FAQ count (defensive, never throws)
    stypes: List[str]
    faq_count: int
    schema_raw: Dict[str, Any]
    try:
        sd_summary, faq_count, schema_raw = _extract_structured_data_summary(html or "", final_url)
        stypes = sd_summary.types
    except Exception:
        stypes, faq_count, schema_raw = [], 0, {}

    # Minimal text extraction for keyphrases and content metrics
    text = ""
    text_len = 0
    try:
        import trafilatura
        text = trafilatura.extract(html or "", output_format="txt", include_comments=False) or ""
        text_len = len(text)
    except Exception:
        pass

    # Keyphrases (lightweight, timeout-bounded)
    phrases: List[Dict[str, Any]] = []
    try:
        top_n = int(os.getenv("KEYPHRASES_TOP_N", "8"))
        timeout_ms = int(os.getenv("KEYPHRASES_TIMEOUT_MS", "2000"))
        kp = extract_keyphrases(text or "", top_n=top_n, timeout_ms=timeout_ms, cache_key=final_url)
        for i, p in enumerate(kp or []):
            phrases.append({
                "phrase": p,
                "weight": max(0.1, 1.0 - i * 0.05),
                "intent": "Local" if (" tx" in (text or "").lower() or " texas" in (text or "").lower()) else "Informational",
            })
    except Exception:
        pass

    # PSI snapshot
    psi_snapshot: Dict[str, Any] = {"performance": None, "seo": None, "accessibility": None, "best_practices": None, "web_vitals": {}}
    try:
        psi = fetch_psi(final_url)
        psi_snapshot.update({
            "performance": psi.get("performance"),
            "seo": psi.get("seo"),
            # Our helper doesn't provide these yet; keep as None for consistent shape
            "accessibility": None,
            "best_practices": None,
            "web_vitals": psi.get("web_vitals", {}),
            "source": psi.get("source", "psi"),
        })
    except Exception:
        pass

    # Build page + business dicts for scoring reuse
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    links_text = [a.get_text(strip=True) for a in soup.find_all("a") if a.get_text(strip=True)]
    out_links = [a.get("href") or "" for a in soup.find_all("a")]
    html_lower = (html or "").lower()

    page = {
        "title": summary.get("title"),
        "meta_description": summary.get("meta_description"),
        "headings": summary.get("headings", {"h1": [], "h2": [], "h3": []}),
        "schema_types": stypes,
        "faq_count": faq_count,
        "internal_links": summary.get("links_internal", 0),
        "external_links": summary.get("links_external", 0),
        "text_len": text_len,
        "links_text": links_text,
        "out_links": out_links,
        "html_lower": html_lower,
    }

    biz = _extract_business_entity(schema_raw, html or "")

    # Compute AEO/GEO scores and weaknesses
    aeo, geo_scores, weaknesses = _compute_scores(page, biz, psi_snapshot)

    # Recommendations (simple derivation from weaknesses + PSI)
    recommendations: List[str] = []
    for w in weaknesses:
        if getattr(w, "fix_summary", None):
            recommendations.append(w.fix_summary)
    # PSI LCP hint
    try:
        lcp = psi_snapshot.get("web_vitals", {}).get("lcp_ms")
        if isinstance(lcp, (int, float)) and lcp >= 2500:
            recommendations.append("Compress hero image, preload critical resources, and target LCP < 2.5s.")
    except Exception:
        pass

    # Missing elements
    missing: List[str] = []
    if not page.get("title"):
        missing.append("title")
    if not page.get("meta_description"):
        missing.append("description")
    if not stypes:
        missing.append("schema")
    if page.get("faq_count", 0) == 0:
        missing.append("faq")

    # Structured data summary
    structured_data_summary = {
        "json_ld_count": getattr(sd_summary, "json_ld_count", 0) if 'sd_summary' in locals() else 0,
        "microdata_count": getattr(sd_summary, "microdata_count", 0) if 'sd_summary' in locals() else 0,
        "opengraph_count": getattr(sd_summary, "opengraph_count", 0) if 'sd_summary' in locals() else 0,
        "types": stypes,
        "faq_count": faq_count,
        "missing_elements": missing,
    }

    # Checkout gating
    checkout = {"status": "skipped_free_test" if payload.free_test_mode else "disabled"}

    # Response assembly
    elapsed_ms = int((time.time() - start) * 1000)
    return AnalyzeUrlResponse(
        target_url=url,
        status="ok",
        page_title=page.get("title"),
        meta_description=page.get("meta_description"),
        final_url=final_url,
        http_status=http_status,
        headings=page.get("headings", {"h1": [], "h2": [], "h3": []}),
        structured_data_summary=structured_data_summary,
        schema_blocks=summary.get("schema_blocks", []),
        nap={
            "name": biz.get("name"),
            "address": biz.get("address"),
            "phone": biz.get("phone"),
        },
        keyphrases=phrases,
        psi_snapshot=psi_snapshot,
        aeo_score=aeo.total,
        geo_score=geo_scores.total,
        aeo_dimensions=[d.model_dump() for d in aeo.dimensions],
        geo_dimensions=[d.model_dump() for d in geo_scores.dimensions],
        weaknesses=[w.model_dump() for w in weaknesses],
        recommendations=recommendations,
        checkout=checkout,
        premium_preview=True,
        timings={"html_ms": html_ms, "total_ms": elapsed_ms},
    )

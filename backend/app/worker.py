"""Background worker for async scan jobs using RQ (Redis Queue).

This module provides job queue infrastructure for offloading long-running
scan operations to background workers, enabling non-blocking API responses.

Usage:
    # Start worker process:
    python -m app.worker

    # Or via RQ CLI:
    rq worker --with-scheduler xenlixai_queue -c app.worker_config
"""
from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel, Field
from typing import Literal

from redis import Redis
from rq import Worker, Queue, Connection

from app.core.config import settings


# ============================
# Report Cards (Lighthouse-style)
# ============================

class ReportCard(BaseModel):
    id: str
    title: str
    score: float = Field(ge=0.0, le=1.0)
    impact: Literal["high", "med", "low"]
    description: str
    suggested_fix: str


def _impact_for_score(score: float) -> Literal["high", "med", "low"]:
    if score < 0.3:
        return "high"
    if score < 0.7:
        return "med"
    return "low"


def _model_to_dict(m: BaseModel) -> Dict[str, Any]:
    # Pydantic v2 prefers model_dump; fallback to dict for v1 compatibility
    try:
        return m.model_dump()  # type: ignore[attr-defined]
    except Exception:
        return m.dict()


def _build_report_cards(
    business: Dict[str, Any],
    psi: Dict[str, Any],
    schema_items: List[Any],
    text: str,
) -> List[Dict[str, Any]]:
    """Derive Lighthouse-style report cards from existing signals.

    Cards:
      - Structured data (schema)
      - SEO (PSI SEO score)
      - Local NAP signals
      - Content depth (thin content)
    """
    cards: List[Dict[str, Any]] = []

    # Structured data
    has_schema = bool(schema_items) or bool(
        business.get("localbusiness_schema_detected") or business.get("organization_schema_detected")
    )
    schema_score = 1.0 if has_schema else 0.0
    cards.append(
        _model_to_dict(
            ReportCard(
                id="schema",
                title="Structured data",
                score=round(schema_score, 2),
                impact=_impact_for_score(schema_score),
                description=(
                    "JSON-LD or microdata detected (LocalBusiness/Organization)"
                    if has_schema
                    else "No structured data detected on the page"
                ),
                suggested_fix=(
                    "Add JSON-LD LocalBusiness with name, address, telephone, and sameAs links"
                    if not has_schema
                    else "Validate schema fields with Google Rich Results Test"
                ),
            )
        )
    )

    # PSI SEO
    seo_raw = psi.get("seo")
    try:
        seo_score = max(0.0, min(1.0, float(seo_raw) / 100.0)) if seo_raw is not None else 0.0
    except Exception:
        seo_score = 0.0
    cards.append(
        _model_to_dict(
            ReportCard(
                id="psi-seo",
                title="SEO (PSI)",
                score=round(seo_score, 2),
                impact=_impact_for_score(seo_score),
                description=(
                    f"PageSpeed Insights SEO score is {seo_raw}"
                    if seo_raw is not None
                    else "PSI SEO score unavailable"
                ),
                suggested_fix=(
                    "Optimize title/meta tags, anchors, and crawlability; address PSI recommendations"
                ),
            )
        )
    )

    # NAP signals
    nap_found = bool(business.get("nap_detected"))
    nap_score = 1.0 if nap_found else 0.0
    cards.append(
        _model_to_dict(
            ReportCard(
                id="nap",
                title="Local NAP signals",
                score=round(nap_score, 2),
                impact=_impact_for_score(nap_score),
                description=(
                    "Business name, phone, and address present"
                    if nap_found
                    else "Business name, phone, and/or address not clearly present"
                ),
                suggested_fix=(
                    "Add visible NAP to the page and mirror it in LocalBusiness JSON-LD"
                    if not nap_found
                    else "Ensure NAP consistency across site and listings"
                ),
            )
        )
    )

    # Content depth
    words = len([w for w in (text or "").split() if w.strip()])
    content_score = min(1.0, words / 600.0)  # 600+ words considered solid baseline
    cards.append(
        _model_to_dict(
            ReportCard(
                id="content-depth",
                title="Content depth",
                score=round(content_score, 2),
                impact=_impact_for_score(content_score),
                description=f"Approx. {words} words extracted from main content",
                suggested_fix=(
                    "Expand primary content to 500–800+ words with clear H1/H2s and local modifiers"
                    if words < 500
                    else "Review headings and internal links to reinforce topical coverage"
                ),
            )
        )
    )

    return cards

logger = logging.getLogger(__name__)


def get_redis_connection() -> Redis:
    """Get Redis connection for job queue."""
    return Redis.from_url(
        os.getenv("REDIS_URL", "redis://redis:6379/0"),
        decode_responses=False,  # RQ handles serialization
    )


def get_queue(name: str | None = None) -> Queue:
    """Get RQ queue instance."""
    return Queue(name or os.getenv("RQ_QUEUE_NAME", "xenlixai_queue"), connection=get_redis_connection())


# ============================
# Background Job Functions
# ============================


def process_scan_job(job_id: str, url: str, user_id: str | None = None) -> dict:
    """Background job: heavy pipeline. Must never run inside request path."""
    from uuid import UUID
    from sqlmodel import Session, select
    from app.core.db import engine
    from app.models import ScanJob
    from app.services.fetcher import fetch_html
    from app.services.lighthouse import fetch_psi
    from app.services.keyphrases import extract_keyphrases
    from app.services.crewai_reasoner import generate_recommendations
    from app.utils.url_validator import validate_url_or_raise, SSRFProtectionError

    logger.info(f"Starting background scan job: {job_id} for {url}")
    start_time = time.time()

    # Validate URL (persist failure to DB instead of returning without update)
    try:
        validate_url_or_raise(url)
    except SSRFProtectionError as e:
        logger.error(f"SSRF validation failed for {url}: {e}")
        with Session(engine) as db:
            job = db.get(ScanJob, job_id)
            if job:
                job.status = "failed"
                job.progress = 100
                job.full_json = {"error": "This URL is blocked. Use a public website."}
                db.add(job)
                db.commit()
        return {"status": "failed", "id": job_id, "error": str(e)}

    # Use configured SQLModel engine
    with Session(engine) as db:
        job = db.get(ScanJob, job_id)
        if not job:
            return {"status": "gone", "id": job_id}

        try:
            # CRAWL
            job.status = "processing"
            job.progress = 5
            db.add(job)
            db.commit()

            import anyio
            timeout_s = int(os.getenv("EXTRACT_TIMEOUT_SECONDS", "20"))
            html, html_ms = anyio.run(fetch_html, url, timeout_s)

            # PARSE
            job.progress = 20
            db.commit()

            import trafilatura
            from bs4 import BeautifulSoup
            import extruct
            import re
            
            text = trafilatura.extract(html or "", output_format="txt", include_comments=False) or ""
            soup = BeautifulSoup(html or "", "html.parser")
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else None
            extract = {"title": title, "text": text}
            
            # Extract structured data
            schema = []
            schema_raw = {}
            try:
                schema_raw = extruct.extract(html or "", base_url=url, syntaxes=["json-ld", "microdata"])
                schema = schema_raw.get("json-ld", [])
            except Exception:
                pass
            
            # Extract business NAP and local SEO signals
            html_lower = (html or "").lower()
            out_links = [a.get("href") or "" for a in soup.find_all("a")]
            
            business_data = {}
            try:
                # Inline simplified business extraction
                biz_name = None
                biz_phone = None
                biz_address = None
                biz_street = None
                biz_city = None
                biz_state = None
                biz_postal = None
                localbusiness_detected = False
                organization_detected = False
                
                # Check JSON-LD
                for item in schema_raw.get("json-ld", []) or []:
                    item_type = item.get("@type")
                    type_list = item_type if isinstance(item_type, list) else [item_type]
                    for t in type_list:
                        if t:
                            t_lower = str(t).lower()
                            if "localbusiness" in t_lower:
                                localbusiness_detected = True
                            if t_lower == "organization":
                                organization_detected = True
                    
                    if any(str(x).lower() in ("organization", "localbusiness") for x in type_list if x):
                        biz_name = biz_name or item.get("name")
                        biz_phone = biz_phone or item.get("telephone")
                        addr = item.get("address") or {}
                        if isinstance(addr, dict):
                            biz_street = biz_street or addr.get("streetAddress")
                            biz_city = biz_city or addr.get("addressLocality")
                            biz_state = biz_state or addr.get("addressRegion")
                            biz_postal = biz_postal or addr.get("postalCode")
                            parts = [biz_street, biz_city, biz_state, biz_postal]
                            biz_address = biz_address or ", ".join([p for p in parts if p]) or None
                
                # Regex fallback
                if not biz_phone:
                    phone_match = re.search(r"(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
                    biz_phone = phone_match.group(0) if phone_match else None
                
                if not biz_postal:
                    zip_match = re.search(r'\b\d{5}(?:-\d{4})?\b', text)
                    biz_postal = zip_match.group(0) if zip_match else None
                
                # Detect platform hints
                all_links = " ".join(out_links + [html_lower])
                google_hint = bool("google.com/maps" in all_links or "maps.google.com" in all_links or "g.page" in all_links)
                apple_hint = bool("maps.apple.com" in all_links or "businessconnect.apple.com" in all_links)
                
                nap_detected = bool(biz_name and biz_phone and (biz_address or (biz_city and biz_state)))
                
                business_data = {
                    "name": biz_name,
                    "phone": biz_phone,
                    "address": biz_address,
                    "street_address": biz_street,
                    "city": biz_city,
                    "state": biz_state,
                    "postal_code": biz_postal,
                    "nap_detected": nap_detected,
                    "localbusiness_schema_detected": localbusiness_detected,
                    "organization_schema_detected": organization_detected,
                    "google_business_hint": google_hint,
                    "apple_business_connect_hint": apple_hint,
                }
            except Exception:
                business_data = {
                    "nap_detected": False,
                    "localbusiness_schema_detected": False,
                    "organization_schema_detected": False,
                    "google_business_hint": False,
                    "apple_business_connect_hint": False,
                }

            # PSI (safe: fetch_psi handles no API key and errors internally)
            job.progress = 55
            db.commit()
            psi_result: Dict[str, Any] = {}
            try:
                psi_result = fetch_psi(url)
            except Exception:
                psi_result = {"available": False, "error": "psi_call_failed"}

            # KEYBERT
            job.progress = 70
            db.commit()
            keyphrases = []

            # ANALYZE / SCORE (could call CrewAI if enabled)
            job.progress = 85
            db.commit()
            insights = {"aeo_score": 0, "geo_score": 0, "weaknesses": [], "recommendations": [], "citations": [], "nap": {}}

            # Persist teaser/full with local SEO signals
            job.teaser_json = {
                "title": extract.get("title"),
                "has_schema": bool(schema),
                "business": {
                    "name": business_data.get("name"),
                    "phone": business_data.get("phone"),
                    "city": business_data.get("city"),
                    "state": business_data.get("state"),
                    "nap_detected": business_data.get("nap_detected", False),
                    "localbusiness_schema_detected": business_data.get("localbusiness_schema_detected", False),
                    "organization_schema_detected": business_data.get("organization_schema_detected", False),
                    "google_business_hint": business_data.get("google_business_hint", False),
                    "apple_business_connect_hint": business_data.get("apple_business_connect_hint", False),
                },
                "psi": {
                    "available": bool(psi_result.get("available")),
                    "performance": psi_result.get("performance"),
                    "seo": psi_result.get("seo"),
                    "lcp_ms": (psi_result.get("web_vitals", {}) or {}).get("lcp_ms"),
                    "cls": (psi_result.get("web_vitals", {}) or {}).get("cls"),
                },
                "keyphrase_count": len(keyphrases or []),
            }
            # Build report cards (Lighthouse-style) from signals
            report_cards = _build_report_cards(
                business=business_data,
                psi=psi_result,
                schema_items=schema,
                text=extract.get("text") or "",
            )

            job.full_json = {
                "visibility_score": insights.get("aeo_score"),
                "geo_score": insights.get("geo_score"),
                "report_cards": report_cards,
                "business": {
                    "name": business_data.get("name"),
                    "phone": business_data.get("phone"),
                    "address": business_data.get("address"),
                    "street_address": business_data.get("street_address"),
                    "city": business_data.get("city"),
                    "state": business_data.get("state"),
                    "postal_code": business_data.get("postal_code"),
                    "nap_detected": business_data.get("nap_detected", False),
                    "localbusiness_schema_detected": business_data.get("localbusiness_schema_detected", False),
                    "organization_schema_detected": business_data.get("organization_schema_detected", False),
                    "google_business_hint": business_data.get("google_business_hint", False),
                    "apple_business_connect_hint": business_data.get("apple_business_connect_hint", False),
                },
                "issues": insights.get("weaknesses"),
                "recommendations": insights.get("recommendations"),
                "citations": insights.get("citations"),
                "psi": {
                    "available": bool(psi_result.get("available")),
                    "performance": psi_result.get("performance"),
                    "seo": psi_result.get("seo"),
                    "lcp_ms": (psi_result.get("web_vitals", {}) or {}).get("lcp_ms"),
                    "cls": (psi_result.get("web_vitals", {}) or {}).get("cls"),
                    # Keep raw vitals for future expansion
                    "web_vitals": psi_result.get("web_vitals"),
                },
                "schema": schema,
            }
            job.status = "done"
            job.progress = 100
            db.add(job)
            db.commit()
            elapsed_ms = int((time.time() - start_time) * 1000)
            # Optionally trigger shallow crawl as a follow-up job
            try:
                if os.getenv("SCAN_SHALLOW_CRAWL", "false").lower() in ("1", "true", "yes"):                
                    q = get_queue()
                    q.enqueue("app.worker.process_shallow_crawl", job_id=job.id, url=url, job_timeout="2m")
            except Exception:
                pass

            logger.info(f"Completed scan job {job_id} in {elapsed_ms}ms")
            return {"status": "done", "id": job_id}
        except Exception as e:
            job.status = "failed"
            job.progress = 100
            job.full_json = job.full_json or {"error": str(e)}
            db.add(job)
            db.commit()
            return {"status": "failed", "id": job_id, "error": str(e)}


def cleanup_expired_jobs() -> int:
    """Scheduled job to clean up expired scan jobs from DB.

    Returns:
        Number of jobs deleted
    """
    from sqlmodel import Session, select
    from app.core.db import engine
    from app.models import ScanJob

    ttl_seconds = int(os.getenv("SCAN_JOB_TTL_SECONDS", "86400"))  # 24h default
    cutoff_time = int(time.time()) - ttl_seconds

    with Session(engine) as session:
        stmt = select(ScanJob).where(ScanJob.created_at < cutoff_time)
        expired = session.exec(stmt).all()
        count = len(expired)
        for job in expired:
            session.delete(job)
        session.commit()

    logger.info(f"Cleaned up {count} expired scan jobs")
    return count


# ============================
# Worker Entry Point
# ============================


def start_worker():
    """Start RQ worker process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting RQ worker for xenlixai_queue...")

    with Connection(get_redis_connection()):
        worker = Worker(["xenlixai_queue"], name=f"xenlixai-worker-{os.getpid()}")
        worker.work(with_scheduler=True, logging_level="INFO")


if __name__ == "__main__":
    start_worker()


# ============================
# Shallow crawl follow-up job
# ============================

def _same_origin(base: str, candidate: str) -> bool:
    try:
        from urllib.parse import urlparse
        b = urlparse(base)
        c = urlparse(candidate)
        return (b.scheme, b.hostname, (b.port or (443 if b.scheme == "https" else 80))) == (
            c.scheme,
            c.hostname,
            (c.port or (443 if c.scheme == "https" else 80)),
        )
    except Exception:
        return False


def _collect_same_origin_links(html: str, base_url: str, limit: int = 5) -> List[str]:
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        soup = BeautifulSoup(html or "", "html.parser")
        links: List[str] = []
        for a in soup.find_all("a"):
            href = a.get("href") or ""
            if not href or href.startswith("#"):
                continue
            full = urljoin(base_url, href)
            if _same_origin(base_url, full):
                links.append(full)
        # Preserve order, uniq
        seen = set()
        uniq: List[str] = []
        for u in links:
            if u in seen:
                continue
            seen.add(u)
            uniq.append(u)
        return uniq[:limit]
    except Exception:
        return []


def _robots_allows(base_url: str, target_url: str, ua: str = "XenlixAI/1.0") -> bool:
    try:
        from urllib.parse import urlparse, urljoin
        import urllib.robotparser as robotparser
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        # Short timeout fetch
        import requests
        try:
            r = requests.get(robots_url, timeout=3)
            if r.status_code >= 400:
                # Treat missing robots as allow
                return True
            rp.parse(r.text.splitlines())
        except Exception:
            # Network issues: be permissive for shallow, or set policy to allow
            return True
        return rp.can_fetch(ua, target_url)
    except Exception:
        return True


def process_shallow_crawl(job_id: int, url: str, max_pages: int = 5) -> dict:
    """Follow-up job: crawl same-origin links depth=1 and store light results.

    Stores results under ScanJob.extra_pages as an array of dicts with:
      { url, title, status, schema_types, aeo_score_partial, geo_score_partial }
    """
    from sqlmodel import Session
    from app.core.db import engine
    from app.models import ScanJob

    logger.info(f"Starting shallow crawl for job {job_id} base {url}")

    # Fetch base page to collect outbound links
    html = ""
    try:
        import httpx
        with httpx.Client(follow_redirects=True, headers={"User-Agent": "XenlixAI/1.0"}, timeout=8) as client:
            r = client.get(url)
            html = r.text or ""
    except Exception:
        html = ""

    links = _collect_same_origin_links(html, url, limit=max_pages)

    results: List[Dict[str, Any]] = []
    try:
        from bs4 import BeautifulSoup
        import httpx
        # Reuse analyzers from orchestrator (safe helpers)
        from app.api.routes.orchestrator import (
            _extract_structured_data_summary,
            _compute_scores,
        )
        for link in links:
            if not _robots_allows(url, link):
                continue
            status_code = None
            page_html = ""
            try:
                with httpx.Client(follow_redirects=True, headers={"User-Agent": "XenlixAI/1.0"}, timeout=8) as client:
                    resp = client.get(link)
                    status_code = resp.status_code
                    page_html = resp.text or ""
            except Exception:
                pass
            # Title
            title = None
            try:
                soup = BeautifulSoup(page_html or "", "html.parser")
                title = soup.title.string if soup.title and soup.title.string else (soup.title.get_text() if soup.title else None)
                if title:
                    title = " ".join(title.split()).strip()[:80]
            except Exception:
                title = None

            # Structured data summary
            try:
                sd_summary, faq_count, _raw = _extract_structured_data_summary(page_html or "", link)
                stypes = sd_summary.types
            except Exception:
                faq_count = 0
                stypes = []

            # Minimal page inputs for partial scores
            page_dict = {
                "schema_types": stypes,
                "faq_count": faq_count,
                "internal_links": 0,
                "text_len": 0,
                "headings": {"h1": [], "h2": [], "h3": []},
                "html_lower": (page_html or "").lower(),
            }
            biz_dict = {"name": None, "phone": None, "address": None, "geo": {"lat": None, "lng": None}}
            psi_stub = {"performance": None}
            try:
                aeo, geo, _weak = _compute_scores(page_dict, biz_dict, psi_stub)
                aeo_total = aeo.total
                geo_total = geo.total
            except Exception:
                aeo_total = 0
                geo_total = 0

            results.append({
                "url": link,
                "title": title,
                "status": status_code,
                "schema_types": stypes,
                "aeo_score_partial": aeo_total,
                "geo_score_partial": geo_total,
            })
    except Exception as e:
        logger.warning(f"shallow crawl encountered an error: {e}")

    # Persist results
    with Session(engine) as db:
        job = db.get(ScanJob, job_id)
        if not job:
            return {"status": "gone", "id": job_id}
        try:
            job.extra_pages = results
            db.add(job)
            db.commit()
        except Exception:
            # Fallback: persist under full_json.extra_pages if column not present yet
            try:
                fj = job.full_json or {}
                fj["extra_pages"] = results
                job.full_json = fj
                db.add(job)
                db.commit()
            except Exception:
                pass

    logger.info(f"Shallow crawl for job {job_id} stored {len(results)} pages")
    return {"status": "done", "id": job_id, "pages": len(results)}

from __future__ import annotations

import re
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    url: str


class AnalyzePreview(BaseModel):
    title: Optional[str] = None
    headings: List[str] = []
    meta: Dict[str, str] = {}


class AnalyzeResponse(BaseModel):
    url: str
    summary: str
    seo: Dict[str, Any]
    snapshot_id: Optional[int] = None
    preview: AnalyzePreview


def _validate_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL must start with http or https")
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="URL must include a hostname")
    return url


def _fetch_html(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "XenlixaiBot/0.1 (+https://example.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            raise HTTPException(status_code=415, detail=f"Unsupported content type: {content_type}")
        # Read up to 1MB for preview
        raw = resp.read(1024 * 1024)
        charset = resp.headers.get_param("charset") if hasattr(resp.headers, "get_param") else None
        encoding = charset or "utf-8"
        return raw.decode(encoding, errors="replace")


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _extract_preview(html: str) -> AnalyzePreview:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    title = _strip_tags(title_match.group(1)) if title_match else None

    headings_raw = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=re.I | re.S)
    headings = [_strip_tags(h) for h in headings_raw][:20]

    # Basic meta tags
    meta: Dict[str, str] = {}
    desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, flags=re.I)
    if desc:
        meta["description"] = _strip_tags(desc.group(1))
    kw = re.search(r'<meta[^>]+name=["\']keywords["\'][^>]+content=["\'](.*?)["\']', html, flags=re.I)
    if kw:
        meta["keywords"] = _strip_tags(kw.group(1))

    return AnalyzePreview(title=title, headings=headings, meta=meta)


@router.post("/", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    url = _validate_url(payload.url)
    try:
        html = _fetch_html(url)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e}")

    preview = _extract_preview(html)

    heading_count = len(preview.headings)
    t = preview.title or "(no title)"
    summary = f"Title: {t}. Found {heading_count} H1-H3 headings."

    seo: Dict[str, Any] = {
        "title_length": len(preview.title) if preview.title else 0,
        "has_description": bool(preview.meta.get("description")),
        "heading_count": heading_count,
    }

    return AnalyzeResponse(url=url, summary=summary, seo=seo, snapshot_id=None, preview=preview)

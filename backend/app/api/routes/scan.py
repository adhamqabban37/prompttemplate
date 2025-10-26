from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


def extract_local(url: str) -> ScanResponse:
    """
    Download HTML and extract metadata using requests + trafilatura + extruct.
    """
    try:
        import trafilatura
        import extruct
        from w3lib.html import get_base_url
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Missing library: {e}")

    headers = {
        "User-Agent": "XenlixAI/1.0 (+https://xenlixai.com)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {e}")

    html = resp.text
    base_url = get_base_url(html, url)

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
        if not title and "og:title" in og:
            title = og["og:title"]
        if not description and "og:description" in og:
            description = og["og:description"]

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


def extract_firecrawl(url: str) -> ScanResponse:
    """
    Use Firecrawl API to scrape and extract metadata.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="FIRECRAWL_API_KEY not configured")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"url": url, "formats": ["markdown", "html"]}

    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Firecrawl API error: {e}")

    # Parse Firecrawl response (adapt as needed)
    result = data.get("data", {})
    markdown_text = result.get("markdown", "")
    html_content = result.get("html", "")
    meta = result.get("metadata", {})

    text_preview = markdown_text[:500] if markdown_text else None
    title = meta.get("title")
    description = meta.get("description")

    # Firecrawl doesn't return structured schemas by default; placeholder
    schemas: List[Dict[str, Any]] = []
    summary = MetadataSummary()

    return ScanResponse(
        url=url,
        title=title,
        description=description,
        text_preview=text_preview,
        schemas=schemas,
        metadata_summary=summary,
    )


@router.post("/", response_model=ScanResponse)
def scan_url(payload: ScanRequest) -> ScanResponse:
    """
    Scan a URL and extract metadata.
    Uses local extraction (trafilatura + extruct) by default.
    If FIRECRAWL_API_KEY is set, uses Firecrawl API instead.
    """
    url = payload.url
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http or https")

    use_firecrawl = bool(os.environ.get("FIRECRAWL_API_KEY"))
    if use_firecrawl:
        return extract_firecrawl(url)
    else:
        return extract_local(url)

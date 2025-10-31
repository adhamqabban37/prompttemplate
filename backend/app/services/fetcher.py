from __future__ import annotations

import json
import logging
import time
from typing import Optional, Any, Dict, List

import httpx
from bs4 import BeautifulSoup, FeatureNotFound

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
        "XenlixAI/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}


async def fetch_html(url: str, timeout: int = 20) -> tuple[str, int]:
    """Fetch HTML for a URL with redirects, headers, and explicit timing.

    Returns a tuple of (html_text, elapsed_ms).
    Raises httpx.HTTPStatusError or httpx.RequestError on failure.
    """
    start = time.time()
    async with httpx.AsyncClient(follow_redirects=True, headers=HEADERS, timeout=timeout) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            elapsed_ms = int((time.time() - start) * 1000)
            logger.info(
                json.dumps(
                    {
                        "event": "html_fetch_success",
                        "url": url,
                        "status_code": resp.status_code,
                        "final_url": str(resp.url),
                        "elapsed_ms": elapsed_ms,
                        "bytes": len(resp.text or ""),
                    }
                )
            )
            return resp.text, elapsed_ms
        except httpx.HTTPStatusError as e:
            elapsed_ms = int((time.time() - start) * 1000)
            content_preview = (e.response.text or "")[:500] if e.response is not None else ""
            logger.warning(
                json.dumps(
                    {
                        "event": "html_fetch_http_error",
                        "url": url,
                        "status_code": e.response.status_code if e.response else None,
                        "elapsed_ms": elapsed_ms,
                        "headers": dict(e.response.headers) if e.response else {},
                        "text_preview": content_preview,
                    }
                )
            )
            raise
        except httpx.RequestError as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.warning(
                json.dumps(
                    {
                        "event": "html_fetch_request_error",
                        "url": url,
                        "error": f"{type(e).__name__}: {e}",
                        "elapsed_ms": elapsed_ms,
                    }
                )
            )
            raise


def _normalize_title(text: str, limit: int = 80) -> str:
    """Collapse whitespace, strip, and trim to limit characters."""
    t = " ".join((text or "").split()).strip()
    return t[:limit] if len(t) > limit else t


def extract_title_with_source(html: str, url: str = "") -> tuple[Optional[str], Optional[str]]:
    """Extract a best-effort title and indicate the source used.

    Priority: <title> → og:title → twitter:title → first <h1> → domain fallback.
    Always normalizes whitespace and trims to 80 chars.
    Returns (title, source) where source is one of: "title", "og:title",
    "twitter:title", "h1", "hostname", or None if not found.
    """
    if not html:
        fb = _extract_hostname_fallback(url) if url else None
        return (_normalize_title(fb) if fb else None, "hostname" if fb else None)

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        logger.warning(f"BeautifulSoup parsing failed: {e}")
        fb = _extract_hostname_fallback(url) if url else None
        return (_normalize_title(fb) if fb else None, "hostname" if fb else None)

    # 1) <title>
    if soup.title:
        raw = soup.title.string if soup.title.string else soup.title.get_text()
        if raw:
            t = _normalize_title(raw)
            if t:
                return (t, "title")

    # 2) og:title
    try:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            t = _normalize_title(str(og.get("content")))
            if t:
                return (t, "og:title")
    except Exception:
        pass

    # 3) twitter:title
    try:
        tw = soup.find("meta", attrs={"name": "twitter:title"})
        if tw and tw.get("content"):
            t = _normalize_title(str(tw.get("content")))
            if t:
                return (t, "twitter:title")
    except Exception:
        pass

    # 4) first <h1>
    try:
        h1 = soup.find("h1")
        if h1:
            t = _normalize_title(h1.get_text())
            if t:
                return (t, "h1")
    except Exception:
        pass

    # 5) hostname fallback
    fb = _extract_hostname_fallback(url) if url else None
    if fb:
        return (_normalize_title(fb), "hostname")

    logger.warning("No title found using any extraction strategy")
    return (None, None)


def extract_title(html: str, url: str = "") -> Optional[str]:
    """Backwards-compatible title extractor (returns only the title)."""
    t, _src = extract_title_with_source(html, url)
    return t


def _extract_hostname_fallback(url: str) -> Optional[str]:
    """Extract a readable title from the hostname."""
    if not url:
        return None
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname or parsed.netloc
        if hostname:
            # Remove www. prefix and capitalize first letter
            hostname = hostname.replace("www.", "")
            # Convert domain to title case (e.g., "example.com" -> "Example.com")
            return hostname.split(".")[0].capitalize() if hostname else None
    except Exception as e:
        logger.warning(f"Hostname extraction failed: {e}")
    return None


# -------------------------------
# Defensive dict access helper
# -------------------------------
def safe_get(obj: Any, key: Any) -> Any:
    """Safely get a key from a dict-like object.

    Returns None unless obj is a dict and the key exists.
    """
    return obj[key] if isinstance(obj, dict) and key in obj else None


def _flatten_list(maybe_list: Any) -> List[Any]:
    """Flatten a list-of-lists one level; return [] if not a list."""
    if not isinstance(maybe_list, list):
        return []
    flat: List[Any] = []
    for it in maybe_list:
        if isinstance(it, list):
            flat.extend(it)
        else:
            flat.append(it)
    return flat


def parse_html_summary(html: str, url: str) -> Dict[str, Any]:
    """Parse HTML into a structured summary for AEO/GEO analysis.

    Always returns a dict with the following keys, never raising on parse errors:
    {
      "title": str | None,
      "meta_description": str | None,
      "headings": {"h1": [...], "h2": [...], "h3": [...]},
      "schema_blocks": [dict],  # JSON-LD blocks (when available)
      "links_internal": int,
      "links_external": int,
      "raw_html": str
    }
    """
    result: Dict[str, Any] = {
        "title": None,
        "title_source": None,
        "meta_description": None,
        "headings": {"h1": [], "h2": [], "h3": []},
        "schema_blocks": [],
        "links_internal": 0,
        "links_external": 0,
        "raw_html": html or "",
    }

    # Short-circuit if no HTML
    if not html:
        t, src = extract_title_with_source(html, url)
        result["title"], result["title_source"] = t, src
        return result

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        logger.warning(f"BeautifulSoup parse failed: {e}")
        result["title"] = extract_title(html, url)
        return result

    # Title and description
    t, src = extract_title_with_source(html, url)
    result["title"], result["title_source"] = t, src
    try:
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            result["meta_description"] = str(md.get("content")).strip()
        elif not result["meta_description"]:
            ogd = soup.find("meta", property="og:description")
            if ogd and ogd.get("content"):
                result["meta_description"] = str(ogd.get("content")).strip()
    except Exception:
        # Non-fatal
        pass

    # Headings
    try:
        def _texts(tag: str) -> List[str]:
            return [t.get_text(strip=True) for t in soup.find_all(tag) if t.get_text(strip=True)]

        result["headings"] = {
            "h1": _texts("h1"),
            "h2": _texts("h2"),
            "h3": _texts("h3"),
        }
    except Exception:
        pass

    # Links internal/external
    try:
        from urllib.parse import urlparse, urljoin
        parsed_host = (urlparse(url).hostname or "").lower()
        internal = 0
        external = 0
        for a in soup.find_all("a"):
            href = a.get("href") or ""
            if not href or href.startswith("#"):
                continue
            full = urljoin(url, href)
            h = (urlparse(full).hostname or "").lower()
            if h and h == parsed_host:
                internal += 1
            elif h:
                external += 1
        result["links_internal"] = internal
        result["links_external"] = external
    except Exception:
        pass

    # Schema: use extruct defensively, and return JSON-LD blocks only in schema_blocks
    try:
        try:
            import extruct  # type: ignore
            from w3lib.html import get_base_url  # type: ignore
        except Exception as e:
            logger.warning(f"extruct not available: {e}")
            return result

        base = get_base_url(html, url) if "get_base_url" in globals() else url
        data = extruct.extract(html, base_url=base, syntaxes=["json-ld", "microdata", "opengraph"]) or {}

        if not isinstance(data, dict):
            logger.warning(f"extruct returned non-dict: {type(data)}")
            data = {}

        json_ld = data.get("json-ld", []) if isinstance(data, dict) else []
        # Normalize unexpected shapes
        if isinstance(json_ld, list):
            # Flatten one level for list-of-lists
            json_ld = _flatten_list(json_ld)
        else:
            json_ld = []

        # Only include dict blocks
        blocks: List[Dict[str, Any]] = [b for b in json_ld if isinstance(b, dict)]
        result["schema_blocks"] = blocks
    except Exception as e:
        logger.warning(f"Schema parse error: {e}")

    return result

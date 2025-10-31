from __future__ import annotations

import time
from fastapi import APIRouter, HTTPException
from app.services.keyphrases import extract_keyphrases
from app.services.lighthouse import fetch_psi

router = APIRouter(prefix="/warmup", tags=["warmup"])


@router.post("/keybert")
def warmup_keybert() -> dict:
    """Preload the sentence-transformers model and return duration."""
    start = time.time()
    # Run a tiny extraction to force model load
    _ = extract_keyphrases("hello world this is a warmup", top_n=3, timeout_ms=2000)
    dur_ms = int((time.time() - start) * 1000)
    return {"ok": True, "duration_ms": dur_ms}


@router.post("/psi")
def warmup_psi(url: str) -> dict:
    """Call PSI for a URL to warm cache/dedup/circuit-breaker paths."""
    start = time.time()
    try:
        res = fetch_psi(url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    dur_ms = int((time.time() - start) * 1000)
    return {"ok": True, "available": bool(res.get("available")), "duration_ms": dur_ms, "from_cache": False}

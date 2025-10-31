"""KeyBERT-based keyphrase extraction service.

Provides a thin wrapper around KeyBERT with:
- Singleton model instance
- Word-length limiting to avoid heavy inputs
- Timeout guard
- Optional Redis cache (set REDIS_URL to enable)
"""
from __future__ import annotations

import hashlib
import os
import time
from functools import lru_cache
from typing import List, Optional


@lru_cache(maxsize=1)
def _kb():
    from keybert import KeyBERT  # lazy import
    # Prefer the prewarmed small model unless overridden
    model_name = os.getenv("KEYBERT_MODEL", "all-MiniLM-L6-v2")
    return KeyBERT(model=model_name)


def _truncate_words(text: str, max_words: int) -> str:
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def _get_redis():
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    try:
        import redis
        return redis.Redis.from_url(url)
    except Exception:
        return None


def extract_keyphrases(
    text: str,
    top_n: int = 8,
    timeout_ms: int = 2000,
    cache_key: Optional[str] = None,
) -> List[str]:
    """Extract keyphrases using KeyBERT.

    - Limits input to KEYPHRASES_TEXT_LIMIT words (default 3000)
    - Returns [] if it exceeds timeout_ms
    - De-duplicates phrases case-insensitively, preserving first casing
    - Uses Redis cache if REDIS_URL is configured
    """
    start = time.time()
    max_words = int(os.getenv("KEYPHRASES_TEXT_LIMIT", "3000"))
    text = _truncate_words(text or "", max_words)

    # Redis cache
    phrases: List[str] = []
    ttl = int(os.getenv("KEYPHRASES_CACHE_TTL_SECONDS", "43200"))  # 12h default
    cache = _get_redis()
    key: Optional[str] = None
    if cache is not None:
        base = cache_key or text[:2048]
        sha = hashlib.sha1(base.encode("utf-8")).hexdigest()
        key = f"kp:{sha}:{top_n}:{max_words}"
        val = cache.get(key)
        if val:
            try:
                phrases = [p for p in val.decode("utf-8").split("\n") if p]
                return phrases
            except Exception:
                pass

    try:
        kw_model = _kb()
        results = kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 3),
            stop_words="english",
            use_maxsum=False,
            use_mmr=True,
            diversity=float(os.getenv("KEYPHRASES_DIVERSITY", "0.6")),
            top_n=top_n,
        )
        # results: List[Tuple[str, score]]
        seen = set()
        for phrase, _score in results:
            p = (phrase or "").strip()
            if not p:
                continue
            lower = p.lower()
            if lower in seen:
                continue
            seen.add(lower)
            phrases.append(p)
    except Exception as e:
        # Log failure with minimal context
        try:
            import logging, json
            logging.getLogger(__name__).warning(json.dumps({
                "event": "keyphrases_error",
                "error": str(e),
            }))
        except Exception:
            pass
        phrases = []

    # Timeout guard (soft: measured after compute)
    elapsed_ms = int((time.time() - start) * 1000)
    # Strict 2s timeout by default
    if timeout_ms > 0 and elapsed_ms > timeout_ms:
        return []

    if cache is not None and key and phrases:
        try:
            cache.setex(key, ttl, "\n".join(phrases))
        except Exception:
            pass

    # Emit basic metrics
    try:
        import logging, json
        logging.getLogger(__name__).info(json.dumps({
            "event": "keyphrases_complete",
            "count": len(phrases),
            "duration_ms": elapsed_ms,
        }))
    except Exception:
        pass

    return phrases

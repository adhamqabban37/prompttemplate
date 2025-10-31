"""LLM factory for CrewAI using a local Ollama endpoint.

This module centralizes creation of a CrewAI LLM client so all agents/share the
same configuration and we can run fully locally without cloud API keys.

Environment variables:
  - MODEL or CREWAI_MODEL: model id, e.g. "ollama/llama3:8b" or 
    "ollama/llama3:70b". Defaults to "ollama/llama3".
  - OLLAMA_HOST: Base URL for Ollama, default depends on environment:
      • Inside Docker:  http://host.docker.internal:11434
      • Outside Docker: http://localhost:11434
  - LLM_TEMPERATURE: float (default 0.2)
  - LLM_MAX_TOKENS: int (default 2000)
"""
from __future__ import annotations

import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


def _running_in_docker() -> bool:
    # Heuristic commonly used to detect Docker
    return os.path.exists("/.dockerenv") or os.path.isfile("/.dockerenv")


def _resolve_base_url(raw: str | None) -> str:
    if raw:
        # If user explicitly configured localhost but we're inside Docker,
        # transparently reroute to host.docker.internal so it can reach the host.
        if raw.startswith("http://localhost:") and _running_in_docker():
            mapped = raw.replace("http://localhost:", "http://host.docker.internal:")
            logger.info(f"LLM base_url mapped for Docker: {raw} -> {mapped}")
            return mapped
        return raw
    # Default by environment
    return "http://host.docker.internal:11434" if _running_in_docker() else "http://localhost:11434"


@lru_cache(maxsize=1)
def get_llm():
    """Return a configured CrewAI LLM client (singleton).

    Uses a local Ollama endpoint by default, no cloud API keys required.
    """
    # Prefer MODEL; fall back to CREWAI_MODEL for backward compatibility
    model = os.getenv("MODEL") or os.getenv("CREWAI_MODEL") or "ollama/llama3"
    base_url = _resolve_base_url(os.getenv("OLLAMA_HOST"))
    try:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    except Exception:
        temperature = 0.2
    try:
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    except Exception:
        max_tokens = 2000

    # Late import to avoid hard dependency when not used
    from crewai import LLM  # type: ignore

    logger.info(
        "Initializing LLM: model=%s base_url=%s temperature=%s max_tokens=%s",
        model,
        base_url,
        temperature,
        max_tokens,
    )
    return LLM(
        model=model,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )

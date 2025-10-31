"""CrewAI reasoning layer for XenlixAI.

This module wraps a lightweight CrewAI/LiteLLM call to generate AEO/GEO
insights and recommendations from a scan payload and lighthouse metrics.

Env:
    MODEL or CREWAI_MODEL - model string (default: 'ollama/llama3')
    OLLAMA_HOST - Ollama host (e.g., http://localhost:11434)

If the model or CrewAI stack is not available, generate_recommendations
returns a graceful fallback message explaining the situation.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import json

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class Recommendation(BaseModel):
    title: str
    type: str
    impact: int = Field(ge=1, le=5)
    effort: int = Field(ge=1, le=5)
    details: str


class InsightsResponse(BaseModel):
    visibility_score_explainer: str
    top_findings: List[str]
    recommendations: List[Recommendation]


def _build_prompt(scan: Dict[str, Any], psi: Dict[str, Any]) -> str:
    # Compact system + user prompt that asks for JSON only
    model_goals = (
        "You are XenlixAI, an assistant that generates concise AEO (Answer Engine Optimization)"
        " and GEO (Local SEO) insights and concrete recommendations.\n"
        "CRITICAL: Return ONLY valid JSON. No markdown code blocks (no ```json or ```), no backticks, no prose.\n"
        " Your entire response MUST be a single JSON object starting with { and ending with }.\n"
        "Schema: {\"visibility_score_explainer\": string, \"top_findings\": string[], \"recommendations\": array}.\n"
        "Each recommendation MUST have: {\"title\": string, \"type\": string, \"impact\": integer, \"effort\": integer, \"details\": string}.\n"
        "Constraints: impact and effort MUST be integers from 1 to 5 (no decimals, no quotes).\n"
        "Example valid format:\n"
        "{\"visibility_score_explainer\":\"SEO score is strong\",\"top_findings\":[\"Finding 1\"],\"recommendations\":[{\"title\":\"Fix meta\",\"type\":\"SEO\",\"impact\":4,\"effort\":2,\"details\":\"Add description\"}]}\n"
    )

    psi_summary = {
        "performance": psi.get("performance"),
        "seo": psi.get("seo"),
        "lcp_ms": psi.get("web_vitals", {}).get("lcp_ms"),
        "inp_ms": psi.get("web_vitals", {}).get("inp_ms"),
        "cls": psi.get("web_vitals", {}).get("cls"),
    }

    # Coerce metadata_summary to a plain dict
    schemas_any = scan.get("metadata_summary") or {}
    if hasattr(schemas_any, "model_dump"):
        schemas = schemas_any.model_dump()
    elif hasattr(schemas_any, "dict"):
        schemas = schemas_any.dict()
    elif isinstance(schemas_any, dict):
        schemas = schemas_any
    else:
        schemas = {}
    has_localbusiness = any(
        (s.get("type") == "json-ld" and ("LocalBusiness" in str(s.get("data")))) for s in scan.get("schemas", [])
    )
    has_faq = any(
        (s.get("type") == "json-ld" and ("FAQPage" in str(s.get("data")) or "Question" in str(s.get("data")))) for s in scan.get("schemas", [])
    )

    text_preview = str(scan.get('text_preview') or '')[:300]
    keyphrases_list = scan.get('keyphrases') or []
    key_topics = ", ".join([str(k) for k in keyphrases_list]) if keyphrases_list else "n/a"
    prompt = (
        f"{model_goals}\n\n"
        f"URL: {scan.get('url')}\n"
        f"Title: {scan.get('title')!r}\n"
        f"Description: {scan.get('description')!r}\n"
        f"TextPreview: {text_preview!r}\n"
        f"Key Topics: {key_topics}\n"
        f"Schemas summary: json_ld_count={schemas.get('json_ld_count')}, microdata_count={schemas.get('microdata_count')}, opengraph_count={schemas.get('opengraph_count')}\n"
        f"Has LocalBusiness: {has_localbusiness}, Has FAQ: {has_faq}\n"
        f"PSI: {psi_summary}\n"
        "Provide 3 top findings and 3-6 prioritized recommendations. Keep JSON compact."
    )

    return prompt


def generate_recommendations(
    scan: Dict[str, Any],
    lighthouse: Dict[str, Any],
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """Generate insights using a local CrewAI LLM via Ollama.

    Returns a validated JSON-like dict. If the local runtime isn't available,
    returns a graceful fallback.
    """
    # Check if AI is enabled
    from app.core.config import settings
    if not settings.CREW_AI_ENABLED:
        logger.info("CrewAI is disabled (CREW_AI_ENABLED=false), returning rule-based fallback")
        return _create_fallback_insights()

    # Use configured timeout if available
    if hasattr(settings, 'LLM_TIMEOUT_SECONDS'):
        timeout_seconds = settings.LLM_TIMEOUT_SECONDS

    # Create prompt
    prompt = _build_prompt(scan, lighthouse)

    # Try to get a local LLM (Ollama) client
    try:
        from app.services.llm_factory import get_llm
        llm = get_llm()
    except Exception as e:
        logger.warning(f"LLM not available: {e}")
        return {
            "visibility_score_explainer": "AI insights unavailable (model/runtime not configured).",
            "top_findings": [],
            "recommendations": [],
        }

    # Call the local model
    try:
        # Wrap the call in a thread to enforce timeout
        def _invoke() -> str:
            # CrewAI/LiteLLM typically exposes a .call() method
            return llm.call(prompt)  # type: ignore[attr-defined]

        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_invoke)
            try:
                text = future.result(timeout=timeout_seconds)
            except FuturesTimeoutError:
                logger.error("LLM call timed out")
                return _create_fallback_insights()

        # Validate raw output before JSON parsing
        if not isinstance(text, str):
            logger.error("LLM returned non-string output")
            return _create_fallback_insights()
        
        raw = text.strip()
        
        # Strip markdown code fences if present (auto-repair)
        if raw.startswith("```"):
            # Remove opening fence (```json or ```)
            lines = raw.split('\n')
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove closing fence (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = '\n'.join(lines).strip()
            logger.info("Auto-repaired: removed markdown code fences from LLM output")
        
        if not raw or raw[0] not in ('{', '['):
            logger.error(f"Invalid JSON format from LLM: {raw[:120]}")
            return _create_fallback_insights()

        # Parse and validate
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing failed: {je}")
            return _create_fallback_insights()

        try:
            validated = InsightsResponse(**parsed)
            return validated.model_dump()
        except ValidationError as ve:
            logger.warning(f"CrewAI output validation failed: {ve}")
            return {"note": "validation_failed", "raw": parsed}

    except Exception as e:
        logger.error(f"Error during CrewAI reasoning: {e}")
        return _create_fallback_insights()


def _create_fallback_insights() -> Dict[str, Any]:
    """Return minimal, safe insights when AI fails."""
    return {
        "visibility_score_explainer": "Technical analysis complete - AI insights temporarily unavailable.",
        "top_findings": [
            "AI analysis unavailable - showing rule-based results only"
        ],
        "recommendations": [],
    }

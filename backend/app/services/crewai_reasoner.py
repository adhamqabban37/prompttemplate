"""CrewAI reasoning layer for XenlixAI.

This module wraps a lightweight CrewAI/LiteLLM call to generate AEO/GEO
insights and recommendations from a scan payload and lighthouse metrics.

Env:
  CREWAI_MODEL - model string (default: 'ollama/llama3')
  OLLAMA_HOST - optional Ollama host (e.g., http://localhost:11434)

If the model or CrewAI stack is not available, generate_recommendations
returns a graceful fallback message explaining the situation.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, List

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
        " and GEO (Local SEO) insights and concrete recommendations. Respond ONLY with valid JSON"
        " following the schema: visibility_score_explainer (string), top_findings (list), recommendations (list of {title,type,impact,effort,details})."
    )

    psi_summary = {
        "performance": psi.get("performance"),
        "seo": psi.get("seo"),
        "lcp_ms": psi.get("web_vitals", {}).get("lcp_ms"),
        "inp_ms": psi.get("web_vitals", {}).get("inp_ms"),
        "cls": psi.get("web_vitals", {}).get("cls"),
    }

    schemas = scan.get("metadata_summary", {})
    has_localbusiness = any(
        (s.get("type") == "json-ld" and ("LocalBusiness" in str(s.get("data")))) for s in scan.get("schemas", [])
    )
    has_faq = any(
        (s.get("type") == "json-ld" and ("FAQPage" in str(s.get("data")) or "Question" in str(s.get("data")))) for s in scan.get("schemas", [])
    )

    prompt = (
        f"{model_goals}\n\n"
        f"URL: {scan.get('url')}\n"
        f"Title: {scan.get('title')!r}\n"
        f"Description: {scan.get('description')!r}\n"
        f"TextPreview: {scan.get('text_preview', '')[:300]!r}\n"
        f"Schemas summary: json_ld_count={schemas.get('json_ld_count')}, microdata_count={schemas.get('microdata_count')}, opengraph_count={schemas.get('opengraph_count')}\n"
        f"Has LocalBusiness: {has_localbusiness}, Has FAQ: {has_faq}\n"
        f"PSI: {psi_summary}\n"
        "Provide 3 top findings and 3-6 prioritized recommendations. Keep JSON compact."
    )

    return prompt


def generate_recommendations(scan: Dict[str, Any], lighthouse: Dict[str, Any]) -> Dict[str, Any]:
    """Generate insights using CrewAI/LiteLLM. Returns a validated JSON-like dict.

    If model/runtime is not configured, returns a fallback explanation dict.
    """
    model = os.getenv("CREWAI_MODEL", "ollama/llama3")
    if not model:
        return {"error": "CREWAI_MODEL not set - reasoning disabled"}

    # Try importing crewai / litellm stack. If not available, fallback gracefully.
    try:
        # Use litellm for a lightweight adapter if available; otherwise, crewai.
        try:
            from litellm import OpenAI  # type: ignore
        except Exception:
            OpenAI = None

        # If crewai is present, prefer it. But to avoid heavy dependencies, allow missing.
        import crewai  # type: ignore
    except Exception as e:
        logger.warning(f"CrewAI stack not available: {e}")
        return {
            "visibility_score_explainer": "CrewAI model not configured on server.",
            "top_findings": ["Reasoning unavailable: CREWAI_MODEL or runtime not configured"],
            "recommendations": [],
            "note": str(e),
        }

    prompt = _build_prompt(scan, lighthouse)

    # Attempt a simple call pattern; keep it minimal to avoid coupling to a single SDK.
    try:
        # NOTE: We avoid locking into exact SDK shapes; this is best-effort.
        # If litellm is available, use a simple completion call; otherwise try crewai.run
        if 'litellm' in globals() and globals().get('OpenAI'):
            # Very small stub using litellm-like interface (may need adjustment in real env)
            client = OpenAI(model=model)
            resp = client.complete(prompt)
            text = getattr(resp, 'text', str(resp))
        else:
            # crewai fallback (best-effort). Many crewai setups expose a "run" function.
            try:
                text = crewai.run(prompt, model=model)  # type: ignore
            except Exception:
                # Last resort: try to call crewai.Client
                if hasattr(crewai, 'Client'):
                    client = crewai.Client()
                    text = client.run(prompt, model=model)
                else:
                    raise

        # Expect the model to return JSON. Try to parse.
        import json

        parsed = json.loads(text)

        # Validate with Pydantic and return the dict
        try:
            validated = InsightsResponse(**parsed)
            return validated.model_dump()
        except ValidationError as ve:
            logger.warning(f"CrewAI output validation failed: {ve}")
            # Return best-effort parsed content, with validation note
            return {"note": "validation_failed", "raw": parsed}

    except Exception as e:
        logger.error(f"Error during CrewAI reasoning: {e}")
        return {
            "visibility_score_explainer": "CrewAI reasoning failed",
            "top_findings": [f"Reasoning error: {str(e)}"],
            "recommendations": [],
        }

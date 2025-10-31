from fastapi import APIRouter, HTTPException
import time
from app.services.llm_factory import get_llm
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
def health() -> dict:
    """Basic health check endpoint."""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "ai_enabled": settings.CREW_AI_ENABLED
    }


@router.get("/llm")
def llm_health() -> dict:
    """Calls the local LLM with a trivial prompt to verify connectivity.

    Returns the raw string to prove end-to-end local inference without cloud keys.
    """
    if not settings.CREW_AI_ENABLED:
        return {"ok": False, "message": "AI disabled via CREW_AI_ENABLED=false"}
    
    try:
        start = time.time()
        llm = get_llm()
        out = llm.call("ping")  # type: ignore[attr-defined]
        duration_ms = int((time.time() - start) * 1000)
        
        if not out or not str(out).strip():
            raise HTTPException(status_code=502, detail="Empty response from LLM")
        return {"ok": True, "response": str(out), "duration_ms": duration_ms}
    except Exception as e:
        # Common failure when Ollama isn't running or not reachable from container
        raise HTTPException(status_code=503, detail=f"LLM not ready: {e}")

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.rules_loader import get_rules

router = APIRouter(prefix="/rules", tags=["rules"]) 


@router.get("/")
def get_rules_status() -> dict:
    try:
        rules, last_mtime = get_rules()
        return {
            "count": len(getattr(rules, "rules", []) or []),
            "rule_ids": [getattr(r, "id", None) for r in rules.rules],
            "last_loaded_mtime": last_mtime,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load rules: {e}")

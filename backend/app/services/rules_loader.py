from __future__ import annotations

import threading
from pathlib import Path
from typing import List, Optional
import time

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


# Pydantic models for validation
class Rule(BaseModel):
    id: str
    title: str
    category: str
    severity: int = Field(ge=1, le=5)
    when: List[str]
    unless: Optional[List[str]] = None
    details: str
    recommendation: str
    score_impact: int = Field(ge=-10, le=10)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"schema", "geo", "content", "technical", "performance", "analytics"}
        if v not in allowed:
            raise ValueError(f"category must be one of {sorted(allowed)}")
        return v


class RulesFile(BaseModel):
    rules: List[Rule]


# Thread-safe cache shared across workers
_lock = threading.Lock()
_cached_rules: Optional[RulesFile] = None
_cached_path: Optional[Path] = None
_cached_mtime: Optional[float] = None


def _default_rules_path() -> Path:
    # Code lives under /app/app/...; project root is /app
    root = Path(__file__).resolve().parents[2]  # /app
    return root / "config" / "aeo_geo_checks.yaml"


def load_rules(path: Optional[str | Path] = None) -> RulesFile:
    p = Path(path) if path else _default_rules_path()
    if not p.exists():
        raise FileNotFoundError(f"Rules file not found at {p}")

    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    try:
        parsed = RulesFile.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Invalid rules YAML: {e}") from e

    return parsed


def get_rules(path: Optional[str | Path] = None) -> tuple[RulesFile, float]:
    global _cached_rules, _cached_path, _cached_mtime

    p = Path(path) if path else _default_rules_path()
    mtime = p.stat().st_mtime if p.exists() else 0.0

    with _lock:
        if _cached_rules is None or _cached_path != p or (_cached_mtime or 0.0) < mtime:
            # Load and cache
            rules = load_rules(p)
            _cached_rules = rules
            _cached_path = p
            _cached_mtime = mtime
        # Return a tuple of rules and when they were last loaded
        return _cached_rules, (_cached_mtime or time.time())

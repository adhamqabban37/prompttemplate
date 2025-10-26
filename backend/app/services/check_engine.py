from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import jmespath


@dataclass
class EvalResult:
    signals: List[str]
    score_delta: int
    recommendations: List[Dict[str, Any]]


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


def _truthy(value: Any) -> bool:
    return bool(value)


def _format(text: str, ctx: Dict[str, Any]) -> str:
    try:
        return text.format_map(_SafeDict(**ctx))
    except Exception:
        return text


def _build_ctx(data: Dict[str, Any]) -> Dict[str, Any]:
    scan = (data or {}).get("scan", {}) or {}
    lh = (data or {}).get("lighthouse", {}) or {}
    webv = lh.get("web_vitals", {}) or {}
    return {
        "url": scan.get("url"),
        "title": scan.get("title"),
        "description": scan.get("description"),
        "performance": lh.get("performance"),
        "seo": lh.get("seo"),
        "lcp_ms": webv.get("lcp_ms"),
        "inp_ms": webv.get("inp_ms"),
        "cls": webv.get("cls"),
        "tbt_ms": webv.get("tbt_ms"),
    }


def evaluate_rules(data: Dict[str, Any], rules_file: Dict[str, Any] | Any) -> Dict[str, Any]:
    # rules_file may be a pydantic model with .rules or a dict
    rules = getattr(rules_file, "rules", None) or rules_file.get("rules", [])

    signals: List[str] = []
    score_delta = 0
    recs: List[Dict[str, Any]] = []

    ctx = _build_ctx(data)

    for r in rules:
        # r may be pydantic model or dict
        if hasattr(r, "model_dump") or hasattr(r, "id"):
            rid = getattr(r, "id", None)
            title = getattr(r, "title", None)
            category = getattr(r, "category", None)
            severity = getattr(r, "severity", 3)
            when = getattr(r, "when", []) or []
            unless = getattr(r, "unless", None)
            details = getattr(r, "details", "")
            recommendation = getattr(r, "recommendation", "")
            impact = getattr(r, "score_impact", 0)
        else:
            rid = r.get("id")
            title = r.get("title")
            category = r.get("category")
            severity = r.get("severity", 3)
            when = r.get("when", [])
            unless = r.get("unless")
            details = r.get("details", "")
            recommendation = r.get("recommendation", "")
            impact = r.get("score_impact", 0)

        # All `when` expressions must be truthy
        all_when = True
        for expr in when:
            try:
                val = jmespath.search(expr, data)
            except Exception:
                val = None
            if not _truthy(val):
                all_when = False
                break

        if not all_when:
            continue

        # If any unless expression is truthy, skip
        if unless:
            skip = False
            for expr in unless:
                try:
                    val = jmespath.search(expr, data)
                except Exception:
                    val = None
                if _truthy(val):
                    skip = True
                    break
            if skip:
                continue

        # Matched
        signals.append(title)
        score_delta += int(impact)
        recs.append(
            {
                "rule_id": rid,
                "title": title,
                "category": category,
                "impact": int(severity),
                "details": _format(details, ctx),
                "recommendation": _format(recommendation, ctx),
            }
        )

    return {"signals": signals, "score_delta": score_delta, "recommendations": recs}

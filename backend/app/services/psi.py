"""PSI helper wrapper (optional) reusing lighthouse.fetch_psi interface.

Provided to satisfy module contract; delegates to lighthouse.fetch_psi.
"""
from __future__ import annotations

from typing import Dict, Any
from app.services.lighthouse import fetch_psi as _fetch


def fetch_psi_with_cache(url: str, strategy: str = "mobile") -> Dict[str, Any]:
    return _fetch(url, strategy=strategy)

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/payments", tags=["payments"])  # /api/v1/payments


class CheckoutRequest(BaseModel):
    plan: str  # "premium_monthly" | "premium_annual"
    returnScanId: Optional[str] = None


class CheckoutResponse(BaseModel):
    checkoutUrl: str


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(body: CheckoutRequest) -> CheckoutResponse:
    """Create Stripe CheckoutSession or return a dev fallback URL.

    In local-dev (no STRIPE_SECRET_KEY), we return frontend success URL with scanId query,
    allowing the UI flow to continue.
    """
    # If Stripe not configured, return a dev fallback URL to frontend success page
    frontend = os.getenv("FRONTEND_PUBLIC_URL") or os.getenv("FRONTEND_HOST") or "http://localhost:5174"
    if not os.getenv("STRIPE_SECRET_KEY"):
        qs = urlencode({"scanId": body.returnScanId or "dev"})
        return CheckoutResponse(checkoutUrl=f"{frontend}/_layout/success?{qs}")

    # TODO: Wire real Stripe session creation. For now, raise to make behavior explicit in non-dev envs.
    raise HTTPException(status_code=501, detail="Stripe not implemented in this environment")


@router.post("/webhook")
def stripe_webhook() -> dict:
    # Placeholder: in real setup verify signature and mark user premium in DB
    return {"received": True}

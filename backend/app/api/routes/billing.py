import os
import stripe
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session
from app.api.deps import get_db
from app.api.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/billing", tags=["billing"]) 

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


class BillingMe(BaseModel):
    premium: bool
    plan: Literal["free", "premium"]
    stripe_checkout_url: Optional[str] = None


@router.get("/me", response_model=BillingMe)
def billing_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return billing status and a ready-to-use checkout URL if not premium.

    Behavior:
    - If user.premium → premium=true, plan=premium, no checkout URL.
    - If Stripe not configured in env → premium=false, plan=free, return a dev/fake checkout URL
      pointing to the frontend (doesn't error).
    - If Stripe is configured → create a Checkout Session and return its URL.
    """
    frontend = (
        os.getenv("FRONTEND_PUBLIC_URL")
        or os.getenv("FRONTEND_HOST")
        or "http://localhost:5174"
    ).rstrip("/")

    if getattr(user, "premium", False):
        return BillingMe(premium=True, plan="premium", stripe_checkout_url=None)

    price_id = os.getenv("STRIPE_PRICE_ID")

    # Dev fallback: no Stripe configured → return a fake/dev checkout URL
    if not price_id or not stripe.api_key:
        dev_url = f"{frontend}/paywall/dev-checkout?plan=premium"
        return BillingMe(premium=False, plan="free", stripe_checkout_url=dev_url)

    # Real Stripe Checkout Session
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{frontend}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{frontend}/paywall/cancel",
        customer_email=getattr(user, "email", None),
        metadata={"user_id": str(getattr(user, "id", ""))},
    )
    return BillingMe(premium=False, plan="free", stripe_checkout_url=session.url)


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        if secret and stripe.api_key:
            event = stripe.Webhook.construct_event(payload, sig_header, secret)
        else:
            event = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    event_type = event.get("type") if isinstance(event, dict) else getattr(event, "type", None)
    data_object = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event.data.object

    if event_type == "checkout.session.completed":
        user_id = data_object.get("metadata", {}).get("user_id")
        if user_id:
            user = db.get(User, int(user_id))
            if user:
                setattr(user, "premium", True)
                db.add(user); db.commit()

    return {"received": True}
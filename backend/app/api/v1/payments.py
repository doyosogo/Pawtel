from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.api.errors import APIError
from app.core.config import Settings
from app.models import User
from app.payments import service, webhooks
from app.payments.gateway import StripeGateway
from app.schemas.bookings import EmptyAction
from app.security.dependencies import (
    Database,
    csrf_for_authenticated_requests,
    request_settings,
    verified_user,
)

router = APIRouter()


def payment_gateway(settings: Annotated[Settings, Depends(request_settings)]):
    return StripeGateway(settings)


class CheckoutOutput(BaseModel):
    payment_attempt_id: UUID
    client_secret: str = Field(repr=False)
    expires_at: datetime


@router.post(
    "/api/v1/bookings/{booking_id}/checkout-session",
    response_model=CheckoutOutput,
    dependencies=[Depends(csrf_for_authenticated_requests)],
)
def checkout(
    booking_id: UUID,
    body: EmptyAction,
    db: Database,
    user: Annotated[User, Depends(verified_user)],
    settings: Annotated[Settings, Depends(request_settings)],
    gateway: Annotated[StripeGateway, Depends(payment_gateway)],
):
    return service.start(db, user.id, booking_id, settings, gateway)


@router.post("/api/v1/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Database,
    settings: Annotated[Settings, Depends(request_settings)],
):
    # Bound input before signature parsing; raw bytes, never reserialized JSON.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 1048576:
            raise APIError(413, "webhook_too_large", "Webhook is too large.")
    event = webhooks.verified_event(
        bytes(body), request.headers.get("Stripe-Signature"), settings
    )
    await run_in_threadpool(webhooks.process, db, event)
    return {"received": True}

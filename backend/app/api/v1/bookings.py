from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings
from app.models import User
from app.models.enums import BookingStatus
from app.payments import service as payment_service
from app.payments.gateway import StripeGateway
from app.schemas.bookings import BookingOutput, BookingRequest, EmptyAction
from app.security.dependencies import (
    Database,
    csrf_for_authenticated_requests,
    request_settings,
    verified_user,
)
from app.services import bookings

UserDep = Annotated[User, Depends(verified_user)]
SettingsDep = Annotated[Settings, Depends(request_settings)]
router = APIRouter(
    prefix="/api/v1/bookings",
    tags=["owner bookings"],
    dependencies=[Depends(verified_user), Depends(csrf_for_authenticated_requests)],
)
host_router = APIRouter(
    prefix="/api/v1/host/bookings",
    tags=["host bookings"],
    dependencies=[Depends(verified_user), Depends(csrf_for_authenticated_requests)],
)


@router.post("", status_code=201, response_model=BookingOutput)
def create(body: BookingRequest, db: Database, user: UserDep):
    return bookings.create(db, user.id, body)


@router.get("", response_model=list[BookingOutput])
def owner_collection(
    db: Database,
    user: UserDep,
    status: BookingStatus | None = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=2147483647),
):
    return bookings.collection(db, user.id, False, status, limit, offset)


@host_router.get("", response_model=list[BookingOutput])
def host_collection(
    db: Database,
    user: UserDep,
    status: BookingStatus | None = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=2147483647),
):
    return bookings.collection(db, user.id, True, status, limit, offset)


@router.get("/{booking_id}", response_model=BookingOutput)
def owner_detail(booking_id: UUID, db: Database, user: UserDep):
    return bookings.detail(db, user.id, booking_id, False)


@host_router.get("/{booking_id}", response_model=BookingOutput)
def host_detail(booking_id: UUID, db: Database, user: UserDep):
    return bookings.detail(db, user.id, booking_id, True)


@router.post("/{booking_id}/cancel", response_model=BookingOutput)
def cancel(
    booking_id: UUID,
    body: EmptyAction,
    db: Database,
    user: UserDep,
    config: SettingsDep,
):
    result = bookings.act(
        db, user.id, booking_id, "cancel", config.booking_payment_window_seconds
    )
    if config.stripe_secret_key and config.stripe_return_url:
        payment_service.cleanup_cancelled(db, booking_id, StripeGateway(config))
    return result


@host_router.post("/{booking_id}/accept", response_model=BookingOutput)
def accept(
    booking_id: UUID,
    body: EmptyAction,
    db: Database,
    user: UserDep,
    config: SettingsDep,
):
    return bookings.act(
        db, user.id, booking_id, "accept", config.booking_payment_window_seconds
    )


@host_router.post("/{booking_id}/decline", response_model=BookingOutput)
def decline(
    booking_id: UUID,
    body: EmptyAction,
    db: Database,
    user: UserDep,
    config: SettingsDep,
):
    return bookings.act(
        db, user.id, booking_id, "decline", config.booking_payment_window_seconds
    )

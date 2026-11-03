"""Pre-payment booking workflows. Lock order: Listing, then Booking."""

from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, joinedload

from app.api.errors import APIError
from app.models import (
    Booking,
    BookingPet,
    Listing,
    ListingAcceptedSpecies,
    PaymentAttempt,
    Pet,
    User,
)
from app.models.enums import BookingStatus, ListingStatus
from app.schemas.bookings import (
    BookingListing,
    BookingOutput,
    BookingPetSummary,
    BookingRequest,
)
from app.schemas.discovery import StayQuery
from app.services.discovery import peak_occupancy
from app.services.pricing import quote


def today_utc() -> date:
    return datetime.now(UTC).date()


def dates_valid(start: date, end: date) -> None:
    if end <= start or start < today_utc():
        raise APIError(
            422,
            "invalid_booking_dates",
            "Use future or current UTC stay dates with checkout after check-in.",
        )


def not_found():
    return APIError(404, "booking_not_found", "Booking not found.")


def scoped(user_id: UUID, host: bool):
    query = select(Booking).join(Listing)
    return (
        query.where(Listing.host_id == user_id)
        if host
        else query.where(Booking.owner_id == user_id)
    )


def output_query(query):
    return query.options(
        joinedload(Booking.listing).load_only(
            Listing.title, Listing.suburb, Listing.state
        ),
        joinedload(Booking.owner).load_only(User.display_name),
        joinedload(Booking.booking_pets).joinedload(BookingPet.pet),
    )


def output(row: Booking) -> BookingOutput:
    return BookingOutput(
        **{
            name: getattr(row, name)
            for name in (
                "id",
                "status",
                "nightly_base_price_cents",
                "additional_pet_price_cents",
                "subtotal_cents",
                "service_fee_cents",
                "total_cents",
                "payment_expires_at",
                "created_at",
                "updated_at",
            )
        },
        check_in=row.start_date,
        check_out=row.end_date,
        owner_display_name=row.owner.display_name,
        listing=BookingListing(
            id=row.listing.id,
            title=row.listing.title,
            suburb=row.listing.suburb,
            state=row.listing.state,
        ),
        pets=[
            BookingPetSummary.model_validate(pair.pet)
            for pair in sorted(row.booking_pets, key=lambda pair: pair.pet_id)
        ],
    )


def read_output(db: Session, query) -> BookingOutput:
    row = db.execute(output_query(query)).unique().scalar_one_or_none()
    if row is None:
        raise not_found()
    return output(row)


def collection(db: Session, user_id: UUID, host: bool, status=None, limit=20, offset=0):
    query = scoped(user_id, host)
    if status is not None:
        query = query.where(Booking.status == status)
    query = (
        query.order_by(Booking.created_at.desc(), Booking.id.desc())
        .limit(limit)
        .offset(offset)
    )
    with db.begin():
        return [
            output(row) for row in db.execute(output_query(query)).unique().scalars()
        ]


def detail(db: Session, user_id: UUID, booking_id: UUID, host: bool):
    with db.begin():
        return read_output(db, scoped(user_id, host).where(Booking.id == booking_id))


def validate_pets(db: Session, owner_id: UUID, pet_ids: list[UUID], listing: Listing):
    pets = list(
        db.scalars(
            select(Pet).where(
                Pet.id.in_(pet_ids), Pet.owner_id == owner_id, Pet.is_active.is_(True)
            )
        )
    )
    if not pet_ids or len(pets) != len(pet_ids):
        raise APIError(422, "pet_not_available", "Selected pets are not available.")
    accepted = set(
        db.scalars(
            select(ListingAcceptedSpecies.species).where(
                ListingAcceptedSpecies.listing_id == listing.id
            )
        )
    )
    if any(pet.species not in accepted for pet in pets):
        raise APIError(
            422, "pet_not_accepted", "Listing does not accept selected pet species."
        )
    return pets


def ensure_capacity(db: Session, listing: Listing, start: date, end: date, count: int):
    stay = StayQuery(check_in=start, check_out=end, pet_count=count)
    peak = peak_occupancy(stay, listing.id)
    occupied = (
        db.scalar(select(peak.c.peak).where(peak.c.listing_id == listing.id)) or 0
    )
    if occupied + count > listing.max_pet_capacity:
        raise APIError(
            409,
            "booking_capacity_unavailable",
            "Capacity is no longer available for this stay.",
        )


def ensure_capacity_floor(db: Session, listing_id: UUID, capacity: int):
    """Caller has already written/locked Listing; do not strand existing holds."""
    bounds = db.execute(
        select(func.min(Booking.start_date), func.max(Booking.end_date)).where(
            Booking.listing_id == listing_id,
            Booking.status.in_(
                [BookingStatus.AWAITING_PAYMENT, BookingStatus.CONFIRMED]
            ),
        )
    ).one()
    if bounds[0] is None:
        return
    peak = peak_occupancy(
        StayQuery(check_in=bounds[0], check_out=bounds[1], pet_count=1), listing_id
    )
    maximum = db.scalar(select(peak.c.peak)) or 0
    if maximum > capacity:
        raise APIError(
            409,
            "listing_capacity_reserved",
            "Capacity cannot be reduced below existing reservations.",
        )


def create(db: Session, owner_id: UUID, data: BookingRequest):
    dates_valid(data.check_in, data.check_out)
    with db.begin():
        listing = db.scalar(
            select(Listing).where(
                Listing.id == data.listing_id, Listing.status == ListingStatus.PUBLISHED
            )
        )
        if listing is None:
            raise APIError(404, "listing_unavailable", "Listing is unavailable.")
        if listing.host_id == owner_id:
            raise APIError(
                422, "self_booking_not_allowed", "You cannot book your own listing."
            )
        pets = validate_pets(db, owner_id, data.pet_ids, listing)
        ensure_capacity(db, listing, data.check_in, data.check_out, len(pets))
        price = quote(
            listing.base_nightly_price_cents,
            listing.additional_pet_price_cents,
            len(pets),
            (data.check_out - data.check_in).days,
        )
        booking = Booking(
            owner_id=owner_id,
            listing_id=listing.id,
            start_date=data.check_in,
            end_date=data.check_out,
            status=BookingStatus.REQUESTED,
            **asdict(price),
            booking_pets=[BookingPet(pet_id=pet.id) for pet in pets],
        )
        db.add(booking)
        db.flush()
        return read_output(db, scoped(owner_id, False).where(Booking.id == booking.id))


# Only pre-payment actors/transitions exist here. No arbitrary client status update.
TRANSITIONS = {
    "accept": {BookingStatus.REQUESTED: BookingStatus.AWAITING_PAYMENT},
    "decline": {BookingStatus.REQUESTED: BookingStatus.DECLINED},
    "cancel": {
        BookingStatus.REQUESTED: BookingStatus.CANCELLED,
        BookingStatus.AWAITING_PAYMENT: BookingStatus.CANCELLED,
        BookingStatus.CANCELLED: BookingStatus.CANCELLED,
    },
}


def transition(row: Booking, action: str, window_seconds: int):
    target = TRANSITIONS[action].get(row.status)
    if target is None:
        raise APIError(
            409,
            "booking_invalid_state",
            "This action is not allowed in the current state.",
        )
    if row.status == target:
        return
    row.status = target
    if action == "accept":
        row.payment_expires_at = datetime.now(UTC) + timedelta(seconds=window_seconds)
    elif action == "cancel":
        # A cancelled unpaid hold has no actionable payment deadline.
        row.payment_expires_at = None


def act(db: Session, user_id: UUID, booking_id: UUID, action: str, window_seconds=1800):
    host = action in {"accept", "decline"}
    try:
        with db.begin():
            # Bound waits; no network/provider work inside this transaction.
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            listing_id = db.scalar(
                scoped(user_id, host)
                .with_only_columns(Booking.listing_id)
                .where(Booking.id == booking_id)
            )
            if listing_id is None:
                raise not_found()
            listing = db.scalar(
                select(Listing)
                .where(
                    Listing.id == listing_id,
                    *([Listing.host_id == user_id] if host else []),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if listing is None:
                raise not_found()
            row = db.scalar(
                scoped(user_id, host)
                .where(Booking.id == booking_id)
                .with_for_update(of=Booking)
                .execution_options(populate_existing=True)
            )
            if row is None:
                raise not_found()
            if row.status not in TRANSITIONS[action]:
                raise APIError(
                    409,
                    "booking_invalid_state",
                    "This action is not allowed in the current state.",
                )
            if action == "accept":
                dates_valid(row.start_date, row.end_date)
                if listing.status != ListingStatus.PUBLISHED:
                    raise APIError(
                        409,
                        "listing_unavailable",
                        "Listing is unavailable for acceptance.",
                    )
                owner = db.scalar(
                    select(User).where(
                        User.id == row.owner_id,
                        User.is_active.is_(True),
                        User.email_verified_at.is_not(None),
                    )
                )
                if owner is None:
                    raise APIError(
                        409,
                        "booking_owner_unavailable",
                        "The booking owner is not eligible.",
                    )
                pet_ids = list(
                    db.scalars(
                        select(BookingPet.pet_id).where(BookingPet.booking_id == row.id)
                    )
                )
                validate_pets(db, row.owner_id, pet_ids, listing)
                ensure_capacity(db, listing, row.start_date, row.end_date, len(pet_ids))
            if action == "cancel":
                for attempt in db.scalars(
                    select(PaymentAttempt)
                    .where(
                        PaymentAttempt.booking_id == row.id,
                        PaymentAttempt.status.in_(["CREATING", "OPEN"]),
                    )
                    .with_for_update()
                ):
                    attempt.status = "REQUIRES_RECONCILIATION"
                    attempt.reconciliation_reason = "CANCEL_CLEANUP_PENDING"
            transition(row, action, window_seconds)
            db.flush()
            return read_output(db, scoped(user_id, host).where(Booking.id == row.id))
    except OperationalError as error:
        if getattr(error.orig, "sqlstate", None) in {"55P03", "40P01", "40001"}:
            raise APIError(
                409, "booking_busy", "Booking is busy; reload before retrying."
            ) from None
        raise

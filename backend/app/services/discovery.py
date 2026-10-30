"""Published-only reads and advisory capacity; no reservations or row locks."""

from sqlalchemy import func, select, union_all
from sqlalchemy.orm import Session, joinedload

from app.api.errors import APIError
from app.models import Booking, BookingPet, HostProfile, Listing, User
from app.models.enums import BookingStatus, ListingStatus
from app.schemas.discovery import (
    Availability,
    ListingPage,
    PublicHost,
    PublicListing,
    SearchQuery,
    StayQuery,
)


def peak_occupancy(stay: StayQuery):
    # Count association rows once per overlapping reserving booking. Clip intervals
    # to the requested stay, then sweep their +/- pet-count events by date.
    stays = (
        select(
            Booking.listing_id,
            func.greatest(Booking.start_date, stay.check_in).label("start"),
            func.least(Booking.end_date, stay.check_out).label("end"),
            func.count(BookingPet.pet_id).label("pets"),
        )
        .join(BookingPet, BookingPet.booking_id == Booking.id)
        .where(
            Booking.status.in_(
                [BookingStatus.AWAITING_PAYMENT, BookingStatus.CONFIRMED]
            ),
            Booking.start_date < stay.check_out,
            Booking.end_date > stay.check_in,
        )
        .group_by(Booking.id)
        .cte("reserved_stays")
    )
    events = union_all(
        select(
            stays.c.listing_id, stays.c.start.label("day"), stays.c.pets.label("delta")
        ),
        select(stays.c.listing_id, stays.c.end.label("day"), -stays.c.pets),
    ).cte("events")
    # Combine arrivals/departures on the same day BEFORE cumulative summation:
    # checkout is exclusive, so adjacent stays never transiently double-count.
    changes = (
        select(
            events.c.listing_id, events.c.day, func.sum(events.c.delta).label("delta")
        )
        .where(events.c.day < stay.check_out)
        .group_by(events.c.listing_id, events.c.day)
        .cte("daily_changes")
    )
    occupancy = select(
        changes.c.listing_id,
        func.sum(changes.c.delta)
        .over(partition_by=changes.c.listing_id, order_by=changes.c.day)
        .label("occupied"),
    ).cte("occupancy")
    return (
        select(occupancy.c.listing_id, func.max(occupancy.c.occupied).label("peak"))
        .group_by(occupancy.c.listing_id)
        .cte("peak_occupancy")
    )


def public_query():
    return select(Listing).where(Listing.status == ListingStatus.PUBLISHED)


def loaded(query):
    return query.options(
        joinedload(Listing.host)
        .load_only(HostProfile.bio)
        .joinedload(HostProfile.user)
        .load_only(User.display_name),
        joinedload(Listing.accepted_species),
    )


def public_output(listing: Listing) -> PublicListing:
    return PublicListing(
        **{
            name: getattr(listing, name)
            for name in (
                "id",
                "title",
                "description",
                "suburb",
                "state",
                "postcode",
                "country_code",
                "base_nightly_price_cents",
                "additional_pet_price_cents",
                "max_pet_capacity",
            )
        },
        accepted_species=sorted(row.species for row in listing.accepted_species),
        host=PublicHost(
            display_name=listing.host.user.display_name, bio=listing.host.bio
        ),
    )


def search(db: Session, filters: SearchQuery) -> ListingPage:
    query = public_query()
    for name in ("state", "postcode"):
        if (value := getattr(filters, name)) is not None:
            query = query.where(getattr(Listing, name) == value)
    if filters.suburb is not None:
        query = query.where(func.lower(Listing.suburb) == filters.suburb.lower())
    for species in filters.species:
        query = query.where(Listing.accepted_species.any(species=species))
    if filters.min_price_cents is not None:
        query = query.where(Listing.base_nightly_price_cents >= filters.min_price_cents)
    if filters.max_price_cents is not None:
        query = query.where(Listing.base_nightly_price_cents <= filters.max_price_cents)
    if filters.pet_count is not None:
        query = query.where(Listing.max_pet_capacity >= filters.pet_count)
    if filters.check_in is not None:
        peak = peak_occupancy(
            StayQuery(
                **filters.model_dump(include={"check_in", "check_out", "pet_count"})
            )
        )
        query = query.outerjoin(peak, peak.c.listing_id == Listing.id).where(
            Listing.max_pet_capacity - func.coalesce(peak.c.peak, 0)
            >= filters.pet_count
        )
    query = loaded(
        query.order_by(Listing.created_at.desc(), Listing.id.desc())
        .offset(filters.offset)
        .limit(filters.limit + 1)
    )
    with db.begin():
        listings = db.execute(query).unique().scalars().all()
        more = len(listings) > filters.limit
        items = [public_output(row) for row in listings[: filters.limit]]
    return ListingPage(
        items=items,
        limit=filters.limit,
        offset=filters.offset,
        has_more=more,
        next_offset=filters.offset + filters.limit if more else None,
    )


def detail(db: Session, listing_id) -> PublicListing:
    with db.begin():
        listing = (
            db.execute(loaded(public_query().where(Listing.id == listing_id)))
            .unique()
            .scalar_one_or_none()
        )
        if listing is None:
            raise APIError(404, "listing_not_found", "Listing not found.")
        return public_output(listing)


def availability(db: Session, listing_id, stay: StayQuery) -> Availability:
    peak = peak_occupancy(stay)
    query = (
        select(Listing.max_pet_capacity - func.coalesce(peak.c.peak, 0))
        .outerjoin(peak, peak.c.listing_id == Listing.id)
        .where(Listing.id == listing_id, Listing.status == ListingStatus.PUBLISHED)
    )
    with db.begin():
        remaining = db.scalar(query)
        if remaining is None:
            raise APIError(404, "listing_not_found", "Listing not found.")
    return Availability(
        **stay.model_dump(),
        listing_id=listing_id,
        available=remaining >= stay.pet_count,
        remaining_capacity_at_tightest_point=max(0, int(remaining)),
    )

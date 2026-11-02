"""Committed rows let independent PostgreSQL connections see race fixtures."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.models import (
    Booking,
    BookingPet,
    HostProfile,
    Listing,
    ListingAcceptedSpecies,
    Pet,
    User,
)
from app.models.enums import BookingStatus
from app.schemas.bookings import BookingRequest
from app.services import bookings

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("capacity,existing,count", [(1, 0, 1), (3, 1, 2)])
def test_simultaneous_accepts_serialize_on_listing(
    db_engine, capacity, existing, count
):
    # db_engine has already checked exact test DB/role, non-superuser and PG18.
    suffix = uuid4().hex
    user_ids = []
    listing_id = None
    first_locked = Event()
    release_first = Event()
    second_ready = Event()
    second_attempting = Event()
    backend_pids = {}
    try:
        with Session(db_engine, expire_on_commit=False) as setup:
            with setup.begin():
                users = [
                    User(
                        email=f"race-{suffix}-{i}@example.test",
                        display_name="Synthetic race user",
                        email_verified_at=datetime.now(UTC),
                    )
                    for i in range(3)
                ]
                setup.add_all(users)
                setup.flush()
                user_ids = [u.id for u in users]
                listing = Listing(
                    host=HostProfile(user_id=user_ids[0]),
                    status="PUBLISHED",
                    title="Race listing",
                    description="Synthetic concurrency fixture",
                    suburb="Norwood",
                    state="SA",
                    postcode="5067",
                    max_pet_capacity=capacity,
                    base_nightly_price_cents=5000,
                    additional_pet_price_cents=1000,
                    accepted_species=[ListingAcceptedSpecies(species="DOG")],
                )
                setup.add(listing)
                setup.flush()
                listing_id = listing.id
                pets = []
                for owner_id in user_ids[1:]:
                    own = [
                        Pet(owner_id=owner_id, name="Race pet", species="DOG")
                        for _ in range(count)
                    ]
                    setup.add_all(own)
                    setup.flush()
                    pets.append([p.id for p in own])
            start = datetime.now(UTC).date() + timedelta(days=10)

            def request_data(ids):
                return BookingRequest(
                    listing_id=listing_id,
                    pet_ids=ids,
                    check_in=start,
                    check_out=start + timedelta(days=3),
                )

            a = bookings.create(setup, user_ids[1], request_data(pets[0]))
            b = bookings.create(setup, user_ids[2], request_data(pets[1]))
            if existing:
                with setup.begin():
                    baseline = Booking(
                        owner_id=user_ids[1],
                        listing_id=listing_id,
                        start_date=start,
                        end_date=start + timedelta(days=3),
                        status="CONFIRMED",
                        nightly_base_price_cents=5000,
                        additional_pet_price_cents=0,
                        subtotal_cents=15000,
                        service_fee_cents=1500,
                        total_cents=16500,
                        booking_pets=[BookingPet(pet_id=pets[0][0])],
                    )
                    setup.add(baseline)

        def run(label, booking_id):
            with db_engine.connect() as connection:
                assert (
                    connection.scalar(text("SHOW transaction_isolation"))
                    == "read committed"
                )
                backend_pids[label] = connection.scalar(text("SELECT pg_backend_pid()"))
                connection.commit()

                def before(conn, cursor, statement, parameters, context, executemany):
                    if (
                        label == "second"
                        and "FOR UPDATE" in statement
                        and "FROM listings" in statement
                    ):
                        second_attempting.set()

                def after(conn, cursor, statement, parameters, context, executemany):
                    if (
                        label == "first"
                        and "FOR UPDATE" in statement
                        and "FROM listings" in statement
                    ):
                        first_locked.set()
                        if not release_first.wait(4):
                            raise RuntimeError("Test did not release first lock")

                event.listen(connection, "before_cursor_execute", before)
                event.listen(connection, "after_cursor_execute", after)
                try:
                    if label == "second":
                        second_ready.set()
                    with Session(bind=connection, expire_on_commit=False) as session:
                        try:
                            result = bookings.act(
                                session, user_ids[0], booking_id, "accept"
                            )
                            return result.status
                        except APIError as error:
                            return error.code
                finally:
                    event.remove(connection, "before_cursor_execute", before)
                    event.remove(connection, "after_cursor_execute", after)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, "first", a.id)
            try:
                assert first_locked.wait(3), (
                    "First acceptance did not acquire Listing lock"
                )
                second = pool.submit(run, "second", b.id)
                assert second_ready.wait(2) and second_attempting.wait(2)
                # Observe actual PostgreSQL blocking, not just overlapping Python calls.
                blocked = False
                deadline = monotonic() + 2
                with db_engine.connect() as observer:
                    while monotonic() < deadline:
                        blockers = observer.scalar(
                            text("SELECT pg_blocking_pids(:pid)"),
                            {"pid": backend_pids["second"]},
                        )
                        if backend_pids["first"] in blockers:
                            blocked = True
                            break
                assert blocked, (
                    "Second acceptance was not blocked by first Listing lock"
                )
                assert backend_pids["first"] != backend_pids["second"]
            finally:
                release_first.set()
            assert first.result(timeout=6) == BookingStatus.AWAITING_PAYMENT
            assert second.result(timeout=6) == "booking_capacity_unavailable"

        with Session(db_engine) as check:
            states = dict(
                check.execute(
                    select(Booking.id, Booking.status).where(
                        Booking.id.in_([a.id, b.id])
                    )
                ).all()
            )
            assert states == {
                a.id: BookingStatus.AWAITING_PAYMENT,
                b.id: BookingStatus.REQUESTED,
            }
            reserved = check.scalar(
                select(func.count())
                .select_from(BookingPet)
                .join(Booking)
                .where(
                    Booking.listing_id == listing_id,
                    Booking.status.in_(
                        [BookingStatus.AWAITING_PAYMENT, BookingStatus.CONFIRMED]
                    ),
                )
            )
            assert reserved == capacity
            loser = check.get(Booking, b.id)
            assert loser.payment_expires_at is None
    finally:
        release_first.set()
        # Only this fixture's committed UUIDs are removed; never truncate shared tables.
        if user_ids:
            with db_engine.begin() as connection:
                ids = select(Booking.id).where(Booking.owner_id.in_(user_ids))
                connection.execute(
                    delete(BookingPet).where(BookingPet.booking_id.in_(ids))
                )
                connection.execute(
                    delete(Booking).where(Booking.owner_id.in_(user_ids))
                )
                if listing_id is not None:
                    connection.execute(
                        delete(ListingAcceptedSpecies).where(
                            ListingAcceptedSpecies.listing_id == listing_id
                        )
                    )
                    connection.execute(delete(Listing).where(Listing.id == listing_id))
                connection.execute(delete(Pet).where(Pet.owner_id.in_(user_ids)))
                connection.execute(
                    delete(HostProfile).where(HostProfile.user_id.in_(user_ids))
                )
                connection.execute(delete(User).where(User.id.in_(user_ids)))

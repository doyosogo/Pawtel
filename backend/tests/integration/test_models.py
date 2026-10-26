from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.models import (
    Booking,
    BookingPet,
    HostProfile,
    Listing,
    ListingAcceptedSpecies,
    Pet,
    User,
)
from app.models.enums import AustralianState, BookingStatus, PetSpecies

pytestmark = pytest.mark.integration


@pytest.fixture
def graph(db_session):
    host_user = User(email="host@example.test", display_name="Host")
    owner = User(email="owner@example.test", display_name="Owner")
    host = HostProfile(user=host_user, bio="Boarding host")
    pet = Pet(owner=owner, name="Milo", species=PetSpecies.DOG)
    listing = Listing(
        host=host,
        title="Adelaide boarding",
        description="Synthetic test listing",
        suburb="Norwood",
        state=AustralianState.SA,
        postcode="5067",
        max_pet_capacity=2,
        base_nightly_price_cents=5000,
        additional_pet_price_cents=1500,
        accepted_species=[ListingAcceptedSpecies(species=PetSpecies.DOG)],
    )
    booking = Booking(
        owner=owner,
        listing=listing,
        start_date=date(2027, 1, 1),
        end_date=date(2027, 1, 3),
        nightly_base_price_cents=5000,
        additional_pet_price_cents=1500,
        subtotal_cents=10000,
        service_fee_cents=1000,
        total_cents=11000,
        booking_pets=[BookingPet(pet=pet)],
    )
    db_session.add(booking)
    db_session.flush()
    return host_user, owner, host, pet, listing, booking


def rejects(session, statement, constraint):
    with pytest.raises(IntegrityError) as caught, session.begin_nested():
        session.execute(statement)
    assert caught.value.orig.diag.constraint_name == constraint


def test_email_normalization_and_uniqueness(db_session):
    db_session.add(User(email="  Owner@Example.Test  ", display_name="Owner"))
    db_session.flush()
    assert db_session.scalar(select(User.email)) == "owner@example.test"
    with pytest.raises(IntegrityError) as caught, db_session.begin_nested():
        db_session.add(User(email="OWNER@example.test", display_name="Duplicate"))
        db_session.flush()
    assert caught.value.orig.diag.constraint_name == "uq_users_email"


@pytest.mark.parametrize(
    "email",
    [
        "UPPER@example.test",
        " leading@example.test",
        "trailing@example.test\t",
        "internal space@example.test",
    ],
)
def test_direct_sql_cannot_bypass_email_normalization(db_session, email):
    rejects(
        db_session,
        insert(User).values(email=email, display_name="U"),
        "ck_users_email_normalized",
    )


def test_host_profile_is_one_to_one(db_session, graph):
    host_user, *_ = graph
    rejects(
        db_session, insert(HostProfile).values(user_id=host_user.id), "pk_host_profiles"
    )


def test_pet_requires_existing_owner(db_session):
    rejects(
        db_session,
        insert(Pet).values(owner_id=uuid4(), name="Cat", species="CAT"),
        "fk_pets_owner_id_users",
    )


@pytest.mark.parametrize("capacity", [0, -1])
def test_listing_capacity_must_be_positive(db_session, graph, capacity):
    listing = graph[4]
    rejects(
        db_session,
        Listing.__table__.update()
        .where(Listing.id == listing.id)
        .values(max_pet_capacity=capacity),
        "ck_listings_capacity_positive",
    )


@pytest.mark.parametrize(
    "field, constraint",
    [
        ("base_nightly_price_cents", "ck_listings_base_price_nonnegative"),
        ("additional_pet_price_cents", "ck_listings_extra_price_nonnegative"),
    ],
)
def test_listing_prices_cannot_be_negative(db_session, graph, field, constraint):
    rejects(
        db_session,
        Listing.__table__.update().where(Listing.id == graph[4].id).values({field: -1}),
        constraint,
    )


def test_accepted_species_pair_unique(db_session, graph):
    rejects(
        db_session,
        insert(ListingAcceptedSpecies).values(listing_id=graph[4].id, species="DOG"),
        "pk_listing_accepted_species",
    )


def test_only_mvp_species_are_valid(db_session, graph):
    with pytest.raises(DataError) as caught, db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO listing_accepted_species (listing_id, species) "
                "VALUES (:id, 'RABBIT')"
            ),
            {"id": graph[4].id},
        )
    assert caught.value.orig.sqlstate == "22P02"


@pytest.mark.parametrize("end", [date(2027, 1, 1), date(2026, 12, 31)])
def test_booking_dates_must_be_ordered(db_session, graph, end):
    rejects(
        db_session,
        Booking.__table__.update()
        .where(Booking.id == graph[5].id)
        .values(end_date=end),
        "ck_bookings_dates_ordered",
    )


def test_booking_pet_pair_unique(db_session, graph):
    rejects(
        db_session,
        insert(BookingPet).values(booking_id=graph[5].id, pet_id=graph[3].id),
        "pk_booking_pets",
    )


@pytest.mark.parametrize(
    "field, constraint",
    [
        ("nightly_base_price_cents", "ck_bookings_base_price_nonnegative"),
        ("additional_pet_price_cents", "ck_bookings_extra_price_nonnegative"),
        ("subtotal_cents", "ck_bookings_subtotal_nonnegative"),
        ("service_fee_cents", "ck_bookings_fee_nonnegative"),
        ("total_cents", "ck_bookings_total_nonnegative"),
    ],
)
def test_price_snapshots_nonnegative(db_session, graph, field, constraint):
    # Keep the arithmetic constraint satisfied so this checks the named invariant.
    values = {field: -1}
    if field == "subtotal_cents":
        values["total_cents"] = 999
    elif field == "service_fee_cents":
        values["total_cents"] = 9999
    elif field == "total_cents":
        # PostgreSQL may check the arithmetic constraint first: test negative total
        # independently by making its parts sum negative as well.
        values["subtotal_cents"] = -1001
    with pytest.raises(IntegrityError) as caught, db_session.begin_nested():
        db_session.execute(
            Booking.__table__.update().where(Booking.id == graph[5].id).values(values)
        )
    if field == "total_cents":
        assert caught.value.orig.diag.constraint_name in {
            "ck_bookings_total_nonnegative",
            "ck_bookings_subtotal_nonnegative",
        }
    else:
        assert caught.value.orig.diag.constraint_name == constraint


def test_snapshot_total_matches_parts(db_session, graph):
    rejects(
        db_session,
        Booking.__table__.update()
        .where(Booking.id == graph[5].id)
        .values(total_cents=999),
        "ck_bookings_total_matches_parts",
    )


def test_payment_hold_needs_deadline(db_session, graph):
    rejects(
        db_session,
        Booking.__table__.update()
        .where(Booking.id == graph[5].id)
        .values(status="AWAITING_PAYMENT"),
        "ck_bookings_payment_hold_has_deadline",
    )
    graph[5].status = BookingStatus.AWAITING_PAYMENT
    graph[5].payment_expires_at = datetime.now(UTC) + timedelta(minutes=30)
    db_session.flush()


@pytest.mark.parametrize(
    "entity, index, constraint",
    [
        (User, 1, "fk_bookings_owner_id_users"),
        (HostProfile, 2, "fk_listings_host_id_host_profiles"),
        (Pet, 3, "fk_booking_pets_pet_id_pets"),
        (Listing, 4, "fk_bookings_listing_id_listings"),
    ],
)
def test_referenced_records_cannot_be_deleted(
    db_session, graph, entity, index, constraint
):
    target = graph[index]
    key = HostProfile.user_id if entity is HostProfile else entity.id
    value = target.user_id if entity is HostProfile else target.id
    # A user with both pets and bookings can hit either restrictive FK first.
    with pytest.raises(IntegrityError) as caught, db_session.begin_nested():
        db_session.execute(delete(entity).where(key == value))
    if entity is User:
        assert caught.value.orig.diag.constraint_name in {
            "fk_bookings_owner_id_users",
            "fk_pets_owner_id_users",
        }
    else:
        assert caught.value.orig.diag.constraint_name == constraint


def test_booking_delete_cascades_association_but_preserves_pet(db_session, graph):
    pet_id, booking_id = graph[3].id, graph[5].id
    db_session.execute(delete(Booking).where(Booking.id == booking_id))
    assert (
        db_session.scalar(select(BookingPet).where(BookingPet.booking_id == booking_id))
        is None
    )
    assert db_session.get(Pet, pet_id) is not None


def test_listing_delete_cascades_species(db_session, graph):
    listing_id = graph[4].id
    db_session.execute(delete(Booking).where(Booking.id == graph[5].id))
    db_session.execute(delete(Listing).where(Listing.id == listing_id))
    assert (
        db_session.scalar(
            select(ListingAcceptedSpecies).where(
                ListingAcceptedSpecies.listing_id == listing_id
            )
        )
        is None
    )


def test_relationships_timestamps_and_price_history(db_session, graph):
    booking_id = graph[5].id
    # Commit a savepoint; the outer test transaction still rolls back.
    db_session.commit()
    db_session.expire_all()
    booking = db_session.get(Booking, booking_id)
    assert booking.owner.email == "owner@example.test"
    assert booking.listing.host.user.email == "host@example.test"
    assert booking.booking_pets[0].pet.owner_id == booking.owner_id
    assert booking.created_at.utcoffset() is not None
    assert booking.updated_at.utcoffset() is not None
    booking.listing.base_nightly_price_cents = 9000
    db_session.flush()
    db_session.expire(booking)
    assert booking.nightly_base_price_cents == 5000
    assert booking.total_cents == 11000


def test_booking_owner_pet_invariant_is_explicitly_not_a_foreign_key(db_session, graph):
    # This records a deliberate service-layer responsibility.
    # It does not define permitted API behaviour.
    foreign_pet = Pet(owner=graph[0], name="Host's cat", species=PetSpecies.CAT)
    db_session.add(BookingPet(booking=graph[5], pet=foreign_pet))
    db_session.flush()
    assert foreign_pet.owner_id != graph[5].owner_id

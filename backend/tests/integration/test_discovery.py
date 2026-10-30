import asyncio
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from app.models import (
    Booking,
    BookingPet,
    HostProfile,
    Listing,
    ListingAcceptedSpecies,
    Pet,
    User,
)
from app.models.enums import BookingStatus, ListingStatus
from app.schemas.discovery import StayQuery
from app.services.discovery import peak_occupancy

pytestmark = pytest.mark.integration


def get(api, path="", **params):
    return asyncio.run(api.client.get("/api/v1/listings" + path, params=params))


@pytest.fixture
def market(db_session):
    user = User(email="private-host@example.test", display_name="Public Host")
    host = HostProfile(user=user, bio="Public bio")
    owner = User(email="private-owner@example.test", display_name="Private Owner")
    db_session.add_all([host, owner])
    db_session.flush()

    def listing(status=ListingStatus.PUBLISHED, species=("DOG", "CAT"), **values):
        row = Listing(
            host=host,
            status=status,
            title="Boarding",
            description="Boarding description",
            suburb="Norwood",
            state="SA",
            postcode="5067",
            max_pet_capacity=3,
            base_nightly_price_cents=5000,
            additional_pet_price_cents=1000,
            accepted_species=[ListingAcceptedSpecies(species=s) for s in species],
        )
        for k, v in values.items():
            setattr(row, k, v)
        db_session.add(row)
        db_session.flush()
        return row

    def booking(row, start=10, end=12, pets=2, status=BookingStatus.CONFIRMED):
        b = Booking(
            owner=owner,
            listing=row,
            start_date=date(2027, 11, start),
            end_date=date(2027, 11, end),
            status=status,
            payment_expires_at=datetime(2027, 11, 1, tzinfo=UTC),
            nightly_base_price_cents=5000,
            additional_pet_price_cents=1000,
            subtotal_cents=10000,
            service_fee_cents=1000,
            total_cents=11000,
            booking_pets=[
                BookingPet(pet=Pet(owner=owner, name="Private pet", species="DOG"))
                for _ in range(pets)
            ],
        )
        db_session.add(b)
        db_session.flush()
        return b

    return listing, booking


def stay(api, row, **params):
    return get(
        api,
        f"/{row.id}/availability",
        **{
            "check_in": "2027-11-10",
            "check_out": "2027-11-14",
            "pet_count": 1,
            **params,
        },
    )


def test_public_visibility_privacy_and_missing(api, market):
    listing, _ = market
    public = listing()
    hidden = [listing(status=s) for s in (ListingStatus.DRAFT, ListingStatus.ARCHIVED)]
    assert [x["id"] for x in get(api).json()["items"]] == [str(public.id)]
    result = get(api, f"/{public.id}")
    assert result.status_code == 200
    assert result.json()["host"] == {"display_name": "Public Host", "bio": "Public bio"}
    assert set(result.json()) == {
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
        "accepted_species",
        "host",
    }
    for row in [*hidden, None]:
        path = f"/{row.id if row else uuid4()}"
        assert get(api, path).json() == {
            "error": {"code": "listing_not_found", "message": "Listing not found."}
        }
        assert get(api, path).status_code == 404
        assert (
            get(
                api,
                path + "/availability",
                check_in="2027-11-10",
                check_out="2027-11-12",
                pet_count=1,
            ).status_code
            == 404
        )


@pytest.mark.parametrize(
    "filters,expected",
    [
        ({"state": "SA"}, 2),
        ({"state": "VIC"}, 0),
        ({"suburb": " norWOOD "}, 2),
        ({"suburb": "Nor"}, 0),
        ({"postcode": "5067"}, 2),
        ({"postcode": "0800"}, 0),
        ({"species": ["DOG"]}, 2),
        ({"species": ["CAT"]}, 1),
        ({"species": ["DOG", "CAT"]}, 1),
        ({"min_price_cents": 6000}, 1),
        ({"max_price_cents": 5000}, 1),
        ({"min_price_cents": 5000, "max_price_cents": 5000}, 1),
        ({"pet_count": 4}, 0),
    ],
)
def test_filters(api, market, filters, expected):
    listing, _ = market
    listing()
    listing(species=("DOG",), base_nightly_price_cents=7000)
    response = get(api, **filters)
    assert response.status_code == 200
    assert len(response.json()["items"]) == expected


@pytest.mark.parametrize(
    "params",
    [
        {"check_in": "2027-11-10"},
        {"check_out": "2027-11-12"},
        {"check_in": "2027-11-10", "check_out": "2027-11-12"},
        {"check_in": "2027-11-10", "check_out": "2027-11-10", "pet_count": 1},
        {"check_in": "2027-11-12", "check_out": "2027-11-10", "pet_count": 1},
        {"pet_count": 0},
        {"pet_count": -1},
        {"pet_count": "1.5"},
        {"limit": 0},
        {"limit": 51},
        {"offset": -1},
        {"min_price_cents": -1},
        {"max_price_cents": "1.5"},
        {"min_price_cents": 5000, "max_price_cents": 1000},
        {"species": "RABBIT"},
        {"species": ["DOG", "DOG"]},
        {"state": "INVALID"},
        {"postcode": "abc"},
        {"suburb": " "},
        {"unknown": "x"},
    ],
)
def test_invalid_filters(api, params):
    response = get(api, **params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_pagination_ties_and_no_duplicates(api, market):
    listing, _ = market
    rows = [listing(created_at=datetime(2027, 1, 1, tzinfo=UTC)) for _ in range(23)]
    expected = sorted((str(x.id) for x in rows), reverse=True)
    page = get(api).json()
    assert [x["id"] for x in page["items"]] == expected[:20]
    assert page["has_more"] and page["next_offset"] == 20
    tail = get(api, offset=20).json()
    assert [x["id"] for x in tail["items"]] == expected[20:]
    assert not tail["has_more"] and tail["next_offset"] is None
    assert [
        x["id"]
        for x in get(api, limit=3, offset=2, species=["DOG", "CAT"]).json()["items"]
    ] == expected[2:5]
    assert get(api, offset=100).json()["items"] == []


@pytest.mark.parametrize("status", list(BookingStatus))
def test_state_capacity(api, market, status):
    listing, booking = market
    row = listing()
    booking(row, pets=3, status=status)
    result = stay(api, row)
    assert result.status_code == 200
    reserved = status in {BookingStatus.CONFIRMED, BookingStatus.AWAITING_PAYMENT}
    assert result.json()["available"] is not reserved
    assert result.json()["remaining_capacity_at_tightest_point"] == (
        0 if reserved else 3
    )
    collection = get(
        api, check_in="2027-11-10", check_out="2027-11-14", pet_count=1
    ).json()
    assert len(collection["items"]) == (0 if reserved else 1)


def test_adjacent_stays_are_not_summed(api, market):
    listing, booking = market
    row = listing()
    booking(row, start=10, end=12, pets=2)
    booking(row, start=12, end=14, pets=2)
    assert stay(api, row).json()["available"]
    assert stay(api, row).json()["remaining_capacity_at_tightest_point"] == 1
    assert not stay(api, row, pet_count=2).json()["available"]
    assert stay(
        api, row, check_in="2027-11-14", check_out="2027-11-15", pet_count=3
    ).json()["available"]


def test_overlaps_multi_pets_clipping_and_advisory(api, market, db_session):
    listing, booking = market
    row = listing()
    booking(row, start=8, end=12, pets=2)
    booking(row, start=11, end=16, pets=1)
    before = db_session.scalar(select(func.count()).select_from(Booking))
    result = stay(api, row).json()
    assert not result["available"]
    assert result["remaining_capacity_at_tightest_point"] == 0
    assert set(result) == {
        "listing_id",
        "check_in",
        "check_out",
        "pet_count",
        "available",
        "remaining_capacity_at_tightest_point",
    }
    assert db_session.scalar(select(func.count()).select_from(Booking)) == before
    assert db_session.scalar(select(func.count()).select_from(BookingPet)) == 3
    assert not db_session.new and not db_session.dirty and not db_session.deleted


def test_empty_and_excess_capacity(api, market):
    listing, _ = market
    row = listing()
    assert stay(api, row, pet_count=3).json()["available"]
    assert not stay(api, row, pet_count=4).json()["available"]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"check_in": "2027-11-10"},
        {"check_in": "2027-11-10", "check_out": "2027-11-10", "pet_count": 1},
        {"check_in": "2027-11-12", "check_out": "2027-11-10", "pet_count": 1},
        {"check_in": "2027-11-10", "check_out": "2027-11-12", "pet_count": 0},
    ],
)
def test_availability_validation(api, market, params):
    listing, _ = market
    assert get(api, f"/{listing().id}/availability", **params).status_code == 422


def test_bounded_query_count_and_sql_shape(api, market, db_session):
    listing, booking = market
    for _ in range(4):
        booking(listing(), pets=1)
    statements = []
    connection = db_session.get_bind()

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("SELECT", "WITH")):
            statements.append(statement)

    event.listen(connection, "before_cursor_execute", capture)
    try:
        assert (
            get(
                api, check_in="2027-11-10", check_out="2027-11-14", pet_count=1
            ).status_code
            == 200
        )
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert len(statements) == 1
    sql = statements[0].upper()
    assert "UNION ALL" in sql and "PARTITION BY" in sql and "FOR UPDATE" not in sql
    assert "JOIN HOST_PROFILES" in sql and "JOIN USERS" in sql
    assert "PASSWORD_HASH" not in sql and "EMAIL_VERIFIED_AT" not in sql
    # Compile the independent aggregate as a second guard on relational structure.
    peak = peak_occupancy(
        StayQuery(
            check_in=date(2027, 11, 10), check_out=date(2027, 11, 14), pet_count=1
        )
    )
    assert "count(booking_pets.pet_id)" in str(select(peak))

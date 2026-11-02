import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select, update

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
from app.services import auth, bookings

pytestmark = pytest.mark.integration


def request(api, method, path, data=None, csrf=True, **kwargs):
    headers = api.csrf() if method != "GET" and csrf else {}
    return asyncio.run(
        api.client.request(
            method,
            "/api/v1" + path,
            headers=kwargs.pop("headers", headers),
            **({"json": data or {}} if method != "GET" else {}),
            **kwargs,
        )
    )


@pytest.fixture
def graph(db_session, make_api, settings):
    def account(email):
        api = make_api()
        registration = api.register(email=email)
        assert registration.status_code == 201
        uid = UUID(registration.json()["user"]["id"])
        with db_session.begin():
            token = auth.issue_verification_token(db_session, uid, settings)
        assert api.post("/verify-email", {"token": token}).status_code == 204
        assert api.login(email=email).status_code == 200
        return api, uid

    host, hid = account("host@example.com")
    owner, oid = account("owner@example.com")
    other, bid = account("other@example.com")
    row = Listing(
        host=HostProfile(user_id=hid),
        status="PUBLISHED",
        title="Boarding",
        description="Test stay",
        suburb="Norwood",
        state="SA",
        postcode="5067",
        max_pet_capacity=3,
        base_nightly_price_cents=5000,
        additional_pet_price_cents=2000,
        accepted_species=[
            ListingAcceptedSpecies(species="DOG"),
            ListingAcceptedSpecies(species="CAT"),
        ],
    )
    pets = [
        Pet(owner_id=oid, name="Milo", species="DOG"),
        Pet(owner_id=oid, name="Luna", species="CAT"),
    ]
    foreign = Pet(owner_id=bid, name="Other", species="DOG")
    db_session.add_all([row, *pets, foreign])
    db_session.flush()
    start = datetime.now(UTC).date() + timedelta(days=10)
    payload = {
        "listing_id": str(row.id),
        "pet_ids": [str(pets[0].id)],
        "check_in": str(start),
        "check_out": str(start + timedelta(days=3)),
    }
    return {
        "host": host,
        "owner": owner,
        "other": other,
        "hid": hid,
        "oid": oid,
        "bid": bid,
        "listing": row,
        "pets": pets,
        "foreign": foreign,
        "payload": payload,
    }


def create(g, **changes):
    r = request(g["owner"], "POST", "/bookings", {**g["payload"], **changes})
    assert r.status_code == 201, r.text
    return r.json()


def action(g, row, name, actor="host"):
    prefix = "/host" if actor == "host" else ""
    return request(g[actor], "POST", f"{prefix}/bookings/{row['id']}/{name}")


def stored(db, bid):
    db.expire_all()
    return db.get(Booking, UUID(bid))


def test_create_quote_and_safe_response(graph, db_session):
    g = graph
    row = create(g, pet_ids=[str(p.id) for p in g["pets"]])
    assert row["status"] == "REQUESTED" and row["payment_expires_at"] is None
    assert [
        row[k]
        for k in (
            "nightly_base_price_cents",
            "additional_pet_price_cents",
            "subtotal_cents",
            "service_fee_cents",
            "total_cents",
        )
    ] == [5000, 2000, 21000, 2100, 23100]
    assert stored(db_session, row["id"]).owner_id == g["oid"]
    assert db_session.scalar(select(func.count()).select_from(BookingPet)) == 2
    assert set(row) == {
        "id",
        "listing",
        "pets",
        "owner_display_name",
        "check_in",
        "check_out",
        "status",
        "nightly_base_price_cents",
        "additional_pet_price_cents",
        "subtotal_cents",
        "service_fee_cents",
        "total_cents",
        "payment_expires_at",
        "created_at",
        "updated_at",
    }
    assert set(row["pets"][0]) == {
        "id",
        "name",
        "species",
        "breed",
        "date_of_birth",
        "is_active",
    }
    assert "email" not in str(row) and "password" not in str(row)


def test_one_pet_and_price_snapshot_preserved(graph, db_session):
    row = create(graph)
    assert row["subtotal_cents"] == 15000 and row["total_cents"] == 16500
    db_session.execute(
        update(Listing)
        .where(Listing.id == graph["listing"].id)
        .values(base_nightly_price_cents=1, additional_pet_price_cents=1)
    )
    db_session.flush()
    accepted = action(graph, row, "accept")
    assert accepted.status_code == 200
    for key in (
        "nightly_base_price_cents",
        "additional_pet_price_cents",
        "subtotal_cents",
        "service_fee_cents",
        "total_cents",
    ):
        assert accepted.json()[key] == row[key]


@pytest.mark.parametrize(
    "field",
    [
        "owner_id",
        "host_id",
        "status",
        "subtotal_cents",
        "service_fee_cents",
        "total_cents",
        "nightly_base_price_cents",
        "additional_pet_price_cents",
        "payment_expires_at",
    ],
)
def test_server_fields_rejected(graph, field):
    r = request(
        graph["owner"], "POST", "/bookings", {**graph["payload"], field: "spoof"}
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "case,code",
    [
        ("empty", "validation_error"),
        ("duplicate", "validation_error"),
        ("foreign", "pet_not_available"),
        ("missing", "pet_not_available"),
        ("archived", "pet_not_available"),
        ("species", "pet_not_accepted"),
        ("capacity", "booking_capacity_unavailable"),
        ("self", "self_booking_not_allowed"),
        ("draft", "listing_unavailable"),
        ("archived_listing", "listing_unavailable"),
        ("missing_listing", "listing_unavailable"),
    ],
)
def test_request_rules(graph, db_session, case, code):
    g = graph
    p = dict(g["payload"])
    if case == "empty":
        p["pet_ids"] = []
    if case == "duplicate":
        p["pet_ids"] *= 2
    if case == "foreign":
        p["pet_ids"] = [str(g["foreign"].id)]
    if case == "missing":
        p["pet_ids"] = [str(uuid4())]
    if case == "archived":
        g["pets"][0].is_active = False
    if case == "species":
        p["pet_ids"] = [str(g["pets"][1].id)]
        db_session.delete(g["listing"].accepted_species[1])
    if case == "capacity":
        p["pet_ids"] = [str(x.id) for x in g["pets"]]
        g["listing"].max_pet_capacity = 1
    if case == "self":
        g["listing"].host_id = g["oid"]
        db_session.add(HostProfile(user_id=g["oid"]))
    if case in {"draft", "archived_listing"}:
        g["listing"].status = "DRAFT" if case == "draft" else "ARCHIVED"
    if case == "missing_listing":
        p["listing_id"] = str(uuid4())
    db_session.flush()
    r = request(g["owner"], "POST", "/bookings", p)
    assert r.status_code in {404, 409, 422}, r.text
    assert r.json()["error"]["code"] == code
    assert db_session.scalar(select(func.count()).select_from(Booking)) == 0


@pytest.mark.parametrize("which", ["same", "before", "past"])
def test_date_rules(graph, which):
    p = dict(graph["payload"])
    if which == "same":
        p["check_out"] = p["check_in"]
    if which == "before":
        p["check_out"] = str(date.fromisoformat(p["check_in"]) - timedelta(days=1))
    if which == "past":
        p["check_in"] = str(datetime.now(UTC).date() - timedelta(days=1))
    r = request(graph["owner"], "POST", "/bookings", p)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_booking_dates"


def test_today_utc_allowed(graph):
    start = datetime.now(UTC).date()
    assert (
        create(graph, check_in=str(start), check_out=str(start + timedelta(days=1)))[
            "status"
        ]
        == "REQUESTED"
    )


def test_owner_host_scope_status_filter_and_no_leaks(graph):
    g = graph
    row = create(g)
    assert request(g["owner"], "GET", "/bookings").json() == [row]
    assert request(g["other"], "GET", "/bookings").json() == []
    assert request(g["host"], "GET", "/host/bookings").json() == [row]
    assert request(g["other"], "GET", "/host/bookings").json() == []
    assert (
        request(
            g["host"], "GET", "/host/bookings", params={"status": "CONFIRMED"}
        ).json()
        == []
    )
    for path in ["/bookings/", "/host/bookings/"]:
        foreign = request(g["other"], "GET", path + row["id"])
        missing = request(g["other"], "GET", path + str(uuid4()))
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json()
    for name in ("accept", "decline"):
        foreign = request(g["other"], "POST", f"/host/bookings/{row['id']}/{name}")
        missing = request(g["other"], "POST", f"/host/bookings/{uuid4()}/{name}")
        assert (
            foreign.status_code == missing.status_code == 404
            and foreign.json() == missing.json()
        )
    assert action(g, row, "cancel", actor="other").status_code == 404


def test_competing_requests_decline_cancel_and_deadline(graph, db_session, settings):
    g = graph
    a = create(g)
    b = create(g)
    assert action(g, a, "decline").json()["status"] == "DECLINED"
    assert action(g, a, "decline").status_code == 409
    assert action(g, a, "accept").status_code == 409
    assert action(g, a, "cancel", actor="owner").status_code == 409
    settings.booking_payment_window_seconds = 600
    before = datetime.now(UTC)
    accepted = action(g, b, "accept")
    assert accepted.status_code == 200
    deadline = datetime.fromisoformat(accepted.json()["payment_expires_at"])
    assert (
        before + timedelta(seconds=settings.booking_payment_window_seconds)
        <= deadline
        <= datetime.now(UTC)
        + timedelta(seconds=settings.booking_payment_window_seconds)
    )
    assert action(g, b, "accept").status_code == 409
    cancelled = action(g, b, "cancel", actor="owner")
    assert (
        cancelled.json()["status"] == "CANCELLED"
        and cancelled.json()["payment_expires_at"] is None
    )
    assert action(g, b, "cancel", actor="owner").json() == cancelled.json()
    c = create(g)
    assert action(g, c, "cancel", actor="owner").json()["status"] == "CANCELLED"
    assert stored(db_session, c["id"]).status == BookingStatus.CANCELLED


@pytest.mark.parametrize(
    "state", ["CONFIRMED", "PAYMENT_FAILED", "COMPLETED", "EXPIRED"]
)
def test_other_states_cannot_act(graph, db_session, state):
    row = create(graph)
    db_session.execute(
        update(Booking).where(Booking.id == UUID(row["id"])).values(status=state)
    )
    db_session.flush()
    for name, who in [("cancel", "owner"), ("accept", "host"), ("decline", "host")]:
        r = action(graph, row, name, actor=who)
        assert (
            r.status_code == 409
            and r.json()["error"]["code"] == "booking_invalid_state"
        )


def test_capacity_recheck_conflict_rollback_and_release(graph, db_session):
    g = graph
    g["listing"].max_pet_capacity = 1
    db_session.flush()
    a = create(g)
    b = create(g)
    assert action(g, a, "accept").status_code == 200
    blocked = action(g, b, "accept")
    assert (
        blocked.status_code == 409
        and blocked.json()["error"]["code"] == "booking_capacity_unavailable"
    )
    failed = stored(db_session, b["id"])
    assert (
        failed.status == BookingStatus.REQUESTED and failed.payment_expires_at is None
    )
    assert request(g["owner"], "POST", "/bookings", g["payload"]).status_code == 409
    assert action(g, a, "cancel", actor="owner").status_code == 200
    assert action(g, b, "accept").status_code == 200


def test_confirmed_and_adjacent_per_night(graph, db_session):
    g = graph
    first = create(g, pet_ids=[str(p.id) for p in g["pets"]])
    db_session.execute(
        update(Booking)
        .where(Booking.id == UUID(first["id"]))
        .values(status="CONFIRMED")
    )
    db_session.flush()
    end = date.fromisoformat(first["check_out"])
    second = create(
        g,
        check_in=str(end),
        check_out=str(end + timedelta(days=3)),
        pet_ids=[str(p.id) for p in g["pets"]],
    )
    assert action(g, second, "accept").status_code == 200
    wide = create(g, check_out=str(end + timedelta(days=3)))
    assert action(g, wide, "accept").status_code == 200
    another = request(g["owner"], "POST", "/bookings", g["payload"])
    assert another.status_code == 409


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("archived", "listing_unavailable"),
        ("draft", "listing_unavailable"),
        ("pet_archived", "pet_not_available"),
        ("species", "pet_not_accepted"),
        ("owner_inactive", "booking_owner_unavailable"),
        ("owner_unverified", "booking_owner_unavailable"),
        ("past", "invalid_booking_dates"),
    ],
)
def test_accept_revalidates(graph, db_session, mutation, code):
    row = create(graph)
    g = graph
    if mutation == "archived":
        g["listing"].status = "ARCHIVED"
    if mutation == "draft":
        g["listing"].status = "DRAFT"
    if mutation == "pet_archived":
        g["pets"][0].is_active = False
    if mutation == "species":
        db_session.delete(g["listing"].accepted_species[0])
    if mutation == "owner_inactive":
        db_session.execute(
            update(User).where(User.id == g["oid"]).values(is_active=False)
        )
    if mutation == "owner_unverified":
        db_session.execute(
            update(User).where(User.id == g["oid"]).values(email_verified_at=None)
        )
    if mutation == "past":
        db_session.execute(
            update(Booking)
            .where(Booking.id == UUID(row["id"]))
            .values(start_date=datetime.now(UTC).date() - timedelta(days=1))
        )
    db_session.flush()
    r = action(g, row, "accept")
    assert r.status_code in {409, 422} and r.json()["error"]["code"] == code
    assert stored(db_session, row["id"]).status == BookingStatus.REQUESTED


OPERATIONS = [
    ("POST", "/bookings"),
    ("GET", "/bookings"),
    ("GET", "/bookings/{id}"),
    ("POST", "/bookings/{id}/cancel"),
    ("GET", "/host/bookings"),
    ("GET", "/host/bookings/{id}"),
    ("POST", "/host/bookings/{id}/accept"),
    ("POST", "/host/bookings/{id}/decline"),
]


@pytest.mark.parametrize("method,path", OPERATIONS)
def test_anonymous_blocked(api, method, path):
    assert request(api, method, path.format(id=uuid4()), csrf=False).status_code == 401


@pytest.mark.parametrize(
    "state,code",
    [("inactive", "account_inactive"), ("unverified", "email_not_verified")],
)
def test_all_operations_account_gate(graph, db_session, state, code):
    g = graph
    row = create(g)
    for uid in [g["oid"], g["hid"]]:
        db_session.execute(
            update(User)
            .where(User.id == uid)
            .values(
                **(
                    {"is_active": False}
                    if state == "inactive"
                    else {"email_verified_at": None}
                )
            )
        )
    db_session.flush()
    for method, path in OPERATIONS:
        api = g["host"] if path.startswith("/host") else g["owner"]
        r = request(
            api,
            method,
            path.format(id=row["id"]),
            g["payload"] if path == "/bookings" else {},
        )
        assert r.status_code == 403 and r.json()["error"]["code"] == code


@pytest.mark.parametrize(
    "path",
    [
        "/bookings",
        "/bookings/{id}/cancel",
        "/host/bookings/{id}/accept",
        "/host/bookings/{id}/decline",
    ],
)
def test_csrf_and_action_body(graph, path):
    row = create(graph)
    g = graph
    api = g["host"] if path.startswith("/host") else g["owner"]
    r = request(
        api,
        "POST",
        path.format(id=row["id"]),
        g["payload"] if path == "/bookings" else {},
        csrf=False,
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
    if path != "/bookings":
        assert (
            request(
                api, "POST", path.format(id=row["id"]), {"status": "CONFIRMED"}
            ).status_code
            == 422
        )


def test_accept_rollback_after_transition(graph, db_session, monkeypatch):
    row = create(graph)
    original = bookings.transition

    def fail(*args):
        original(*args)
        raise RuntimeError("Synthetic failure before commit")

    monkeypatch.setattr(bookings, "transition", fail)
    assert action(graph, row, "accept").status_code == 500
    stored_row = stored(db_session, row["id"])
    assert (
        stored_row.status == BookingStatus.REQUESTED
        and stored_row.payment_expires_at is None
    )


def test_create_rollback_association_failure(graph, db_session):
    def fail(*args):
        raise RuntimeError("Synthetic association failure")

    event.listen(BookingPet, "before_insert", fail)
    try:
        assert (
            request(graph["owner"], "POST", "/bookings", graph["payload"]).status_code
            == 500
        )
    finally:
        event.remove(BookingPet, "before_insert", fail)
    assert db_session.scalar(select(func.count()).select_from(Booking)) == 0


def test_capacity_edit_cannot_strand_holds(graph, db_session):
    g = graph
    row = create(g, pet_ids=[str(p.id) for p in g["pets"]])
    assert action(g, row, "accept").status_code == 200
    response = request(
        g["host"],
        "PATCH",
        f"/host/listings/{g['listing'].id}",
        {"max_pet_capacity": 1, "title": "Not retained"},
    )
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "listing_capacity_reserved"
    )
    db_session.expire_all()
    assert db_session.get(Listing, g["listing"].id).max_pet_capacity == 3
    assert db_session.get(Listing, g["listing"].id).title == "Boarding"
    assert action(g, row, "cancel", actor="owner").status_code == 200
    assert (
        request(
            g["host"],
            "PATCH",
            f"/host/listings/{g['listing'].id}",
            {"max_pet_capacity": 1},
        ).status_code
        == 200
    )


@pytest.mark.parametrize("mode", ["invalid", "cross_session"])
@pytest.mark.parametrize(
    "path",
    [
        "/bookings",
        "/bookings/{id}/cancel",
        "/host/bookings/{id}/accept",
        "/host/bookings/{id}/decline",
    ],
)
def test_wrong_csrf_rejected(graph, mode, path):
    row = create(graph)
    api = graph["host"] if path.startswith("/host") else graph["owner"]
    headers = {"X-CSRF-Token": "x" * 43} if mode == "invalid" else graph["other"].csrf()
    response = request(
        api,
        "POST",
        path.format(id=row["id"]),
        graph["payload"] if path == "/bookings" else {},
        csrf=False,
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_two_actual_hosts_have_isolated_inboxes(graph, db_session):
    g = graph
    first = create(g)
    second_listing = Listing(
        host=HostProfile(user_id=g["bid"]),
        status="PUBLISHED",
        title="Other Host",
        description="Synthetic accommodation",
        suburb="Adelaide",
        state="SA",
        postcode="5000",
        max_pet_capacity=2,
        base_nightly_price_cents=1000,
        additional_pet_price_cents=0,
        accepted_species=[ListingAcceptedSpecies(species="DOG")],
    )
    db_session.add(second_listing)
    db_session.flush()
    second = create(g, listing_id=str(second_listing.id))
    assert request(g["host"], "GET", "/host/bookings").json() == [first]
    assert request(g["other"], "GET", "/host/bookings").json() == [second]
    for actor, foreign in [("host", second), ("other", first)]:
        assert (
            request(g[actor], "GET", f"/host/bookings/{foreign['id']}").status_code
            == 404
        )
        assert (
            request(
                g[actor], "POST", f"/host/bookings/{foreign['id']}/accept"
            ).status_code
            == 404
        )
    assert request(g["host"], "GET", f"/host/bookings/{first['id']}").json() == first


def test_quote_rounding_persisted_and_large_quote_rejected(graph, db_session):
    g = graph
    g["listing"].base_nightly_price_cents = 5
    db_session.flush()
    row = create(
        g,
        check_out=str(date.fromisoformat(g["payload"]["check_in"]) + timedelta(days=1)),
    )
    assert (
        row["subtotal_cents"] == 5
        and row["service_fee_cents"] == 1
        and row["total_cents"] == 6
    )
    g["listing"].base_nightly_price_cents = 9007199254740991
    db_session.flush()
    response = request(g["owner"], "POST", "/bookings", g["payload"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "booking_price_out_of_range"
    assert db_session.scalar(select(func.count()).select_from(Booking)) == 1


def test_collection_order_pagination_and_invalid_path(graph):
    a = create(graph)
    b = create(graph)
    expected = sorted(
        [a, b], key=lambda row: (row["created_at"], row["id"]), reverse=True
    )
    assert request(graph["owner"], "GET", "/bookings").json() == expected
    assert (
        request(
            graph["owner"], "GET", "/bookings", params={"limit": 1, "offset": 1}
        ).json()
        == expected[1:]
    )
    assert request(graph["owner"], "GET", "/bookings/not-a-uuid").status_code == 422
    assert (
        request(graph["owner"], "GET", "/bookings", params={"limit": 51}).status_code
        == 422
    )


def test_accept_rollback_after_sql_flush(graph, db_session, monkeypatch):
    row = create(graph)
    original = bookings.read_output

    def fail_after_flush(*args):
        result = original(*args)
        assert result.status == BookingStatus.AWAITING_PAYMENT
        raise RuntimeError("Synthetic failure after SQL flush")

    monkeypatch.setattr(bookings, "read_output", fail_after_flush)
    assert action(graph, row, "accept").status_code == 500
    current = stored(db_session, row["id"])
    assert current.status == BookingStatus.REQUESTED
    assert current.payment_expires_at is None

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select, update

from app.models import Pet, User

pytestmark = pytest.mark.integration


@pytest.fixture
def owners(make_api):
    a, b = make_api(), make_api()
    ids = []
    for api, email in [(a, "pet-owner-a@example.com"), (b, "pet-owner-b@example.com")]:
        registration = api.register(email=email)
        assert registration.status_code == 201
        ids.append(UUID(registration.json()["user"]["id"]))
        assert api.login(email=email).status_code == 200
    return a, b, *ids


def request(api, method, suffix="", data=None, *, csrf=True, headers=None):
    metadata = {}
    if method in {"POST", "PATCH", "DELETE"} and csrf:
        metadata.update(api.csrf())
    metadata.update(headers or {})
    kwargs = {"headers": metadata}
    if method in {"POST", "PATCH", "DELETE"}:
        kwargs["json"] = {} if data is None else data
    return asyncio.run(api.client.request(method, "/api/v1/pets" + suffix, **kwargs))


def create(api, **changes):
    response = request(api, "POST", data={"name": "Milo", "species": "DOG", **changes})
    assert response.status_code == 201
    return response.json()


def stored(db, pet_id):
    db.expire_all()
    return db.scalar(select(Pet).where(Pet.id == UUID(pet_id)))


@pytest.mark.parametrize(
    "method, suffix, data",
    [
        ("GET", "", None),
        ("POST", "", {"name": "Milo", "species": "DOG"}),
        ("GET", "/{id}", None),
        ("PATCH", "/{id}", {"name": "Changed"}),
        ("DELETE", "/{id}", {}),
    ],
)
def test_every_pet_operation_requires_authentication(make_api, method, suffix, data):
    guest = make_api()
    response = request(guest, method, suffix.format(id=uuid4()), data, csrf=False)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_create_assigns_authenticated_owner_and_exposes_safe_fields(owners, db_session):
    a, _, a_id, _ = owners
    response = request(
        a,
        "POST",
        data={
            "name": "  Milo  ",
            "species": "DOG",
            "breed": " Labrador ",
            "date_of_birth": "2020-01-02",
        },
    )
    assert response.status_code == 201
    pet = response.json()
    assert set(pet) == {
        "id",
        "name",
        "species",
        "breed",
        "date_of_birth",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert pet["name"] == "Milo" and pet["breed"] == "Labrador"
    assert pet["date_of_birth"] == "2020-01-02" and pet["is_active"]
    assert stored(db_session, pet["id"]).owner_id == a_id
    assert datetime.fromisoformat(pet["created_at"]).utcoffset() is not None
    for secret_field in [
        "owner_id",
        "owner",
        "password_hash",
        "auth_sessions",
        "email_verified_at",
    ]:
        assert secret_field not in pet
    assert response.headers["cache-control"] == "no-store"


def test_client_cannot_choose_even_its_own_owner_id(owners, db_session):
    a, _, a_id, b_id = owners
    for owner_id in (a_id, b_id):
        response = request(
            a,
            "POST",
            data={
                "name": "Spoof",
                "species": "CAT",
                "owner_id": str(owner_id),
            },
        )
        assert response.status_code == 422
    assert db_session.scalar(select(Pet)) is None


def test_list_is_owner_scoped_and_deterministic(owners):
    a, b, *_ = owners
    mine = [create(a, name="Zulu"), create(a, name="Alpha")]
    foreign = create(b, name="Private B")
    response = request(a, "GET")
    assert response.status_code == 200
    expected = sorted(mine, key=lambda pet: (pet["created_at"], pet["id"]))
    assert [pet["id"] for pet in response.json()] == [pet["id"] for pet in expected]
    assert request(a, "GET").json() == response.json()
    assert [pet["id"] for pet in request(b, "GET").json()] == [foreign["id"]]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "method, data",
    [
        ("GET", None),
        ("PATCH", {"name": "Intrusion"}),
        ("DELETE", {}),
    ],
)
def test_foreign_and_nonexistent_pet_have_identical_private_not_found(
    owners, db_session, method, data
):
    a, b, *_ = owners
    pet = create(a)
    denied = request(b, method, "/" + pet["id"], data)
    missing = request(b, method, "/" + str(uuid4()), data)
    assert denied.status_code == missing.status_code == 404
    assert (
        denied.json()
        == missing.json()
        == {"error": {"code": "pet_not_found", "message": "Pet not found."}}
    )
    assert stored(db_session, pet["id"]).name == "Milo"
    assert stored(db_session, pet["id"]).is_active
    assert request(a, "GET", "/" + pet["id"]).status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "  \t\u2003 "},
        {"name": "x" * 81},
        {"name": None},
        {"species": "RABBIT"},
        {"species": "dog"},
        {"species": None},
        {"breed": "x" * 101},
        {"date_of_birth": "2020-02-30"},
        {"date_of_birth": "2020-01-01T00:00:00"},
        {"date_of_birth": 0},
    ],
)
def test_creation_validates_profile_inputs(owners, changes):
    a, *_ = owners
    response = request(a, "POST", data={"name": "Milo", "species": "DOG", **changes})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert request(a, "GET").json() == []


def test_future_birth_date_rejected_on_create_and_patch(owners):
    a, *_ = owners
    tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    assert (
        request(
            a,
            "POST",
            data={"name": "Milo", "species": "DOG", "date_of_birth": tomorrow},
        ).status_code
        == 422
    )
    pet = create(a)
    assert (
        request(a, "PATCH", "/" + pet["id"], {"date_of_birth": tomorrow}).status_code
        == 422
    )
    assert request(a, "GET", "/" + pet["id"]).json()["date_of_birth"] is None


def test_valid_partial_update_and_nullable_clearing(owners, db_session):
    a, _, a_id, _ = owners
    pet = create(a, breed="Labrador", date_of_birth="2020-01-02")
    suffix = "/" + pet["id"]
    changed = request(a, "PATCH", suffix, {"name": "  Cleo ", "species": "CAT"})
    assert changed.status_code == 200
    assert changed.json()["name"] == "Cleo" and changed.json()["species"] == "CAT"
    assert changed.json()["breed"] == "Labrador"
    assert changed.json()["date_of_birth"] == "2020-01-02"
    cleared = request(a, "PATCH", suffix, {"breed": "  ", "date_of_birth": None})
    assert cleared.status_code == 200
    assert cleared.json()["breed"] is None and cleared.json()["date_of_birth"] is None
    row = stored(db_session, pet["id"])
    assert row.owner_id == a_id and row.name == "Cleo"
    assert cleared.json()["id"] == pet["id"]
    assert cleared.json()["created_at"] == pet["created_at"]


@pytest.mark.parametrize(
    "field, value",
    [
        ("owner_id", "other"),
        ("id", "other"),
        ("created_at", "2000-01-01T00:00:00Z"),
        ("updated_at", "2000-01-01T00:00:00Z"),
        ("is_active", False),
    ],
)
def test_immutable_and_archive_fields_cannot_be_set_by_patch(
    owners, db_session, field, value
):
    a, _, a_id, b_id = owners
    pet = create(a)
    actual = (
        str(b_id) if field == "owner_id" else str(uuid4()) if field == "id" else value
    )
    response = request(
        a, "PATCH", "/" + pet["id"], {field: actual, "name": "Intrusion"}
    )
    assert response.status_code == 422
    row = stored(db_session, pet["id"])
    assert row.owner_id == a_id and row.name == "Milo" and row.is_active


@pytest.mark.parametrize(
    "changes",
    [{}, {"name": None}, {"species": None}, {"name": "  "}, {"species": "dog"}],
)
def test_empty_or_invalid_patch_rejected_without_partial_changes(owners, changes):
    a, *_ = owners
    pet = create(a)
    response = request(a, "PATCH", "/" + pet["id"], changes)
    assert response.status_code == 422
    assert request(a, "GET", "/" + pet["id"]).json() == pet


def test_nonempty_same_value_patch_is_a_valid_update(owners):
    a, *_ = owners
    pet = create(a)
    response = request(a, "PATCH", "/" + pet["id"], {"name": "Milo"})
    assert response.status_code == 200 and response.json()["name"] == "Milo"
    assert datetime.fromisoformat(
        response.json()["updated_at"]
    ) >= datetime.fromisoformat(pet["updated_at"])


def test_archive_preserves_row_filters_lists_and_is_idempotent(owners, db_session):
    a, b, a_id, _ = owners
    pet = create(a)
    active = create(a, name="Active cat", species="CAT")
    foreign = create(b)
    suffix = "/" + pet["id"]
    assert request(a, "DELETE", suffix).status_code == 204
    row = stored(db_session, pet["id"])
    assert row is not None and not row.is_active and row.owner_id == a_id
    archived = request(a, "GET", suffix)
    assert archived.status_code == 200 and not archived.json()["is_active"]
    assert [p["id"] for p in request(a, "GET").json()] == [active["id"]]
    assert {p["id"] for p in request(a, "GET", "?include_archived=true").json()} == {
        pet["id"],
        active["id"],
    }
    assert [p["id"] for p in request(b, "GET", "?include_archived=true").json()] == [
        foreign["id"]
    ]
    timestamp = row.updated_at
    assert request(a, "DELETE", suffix).status_code == 204
    assert stored(db_session, pet["id"]).updated_at == timestamp
    assert request(b, "GET", suffix).status_code == 404
    # Archived metadata can be corrected, but no restore field is exposed.
    correction = request(a, "PATCH", suffix, {"name": "Corrected"})
    assert correction.status_code == 200 and not correction.json()["is_active"]
    assert request(a, "PATCH", suffix, {"is_active": True}).status_code == 422


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_invalid_uuid_has_consistent_safe_validation_error(owners, method):
    a, *_ = owners
    response = request(a, method, "/not-a-uuid", {"name": "Changed"})
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "message": "Invalid request data."}
    }


@pytest.mark.parametrize(
    "method, suffix, data",
    [
        ("GET", "", None),
        ("POST", "", {"name": "Milo", "species": "DOG"}),
        ("GET", "/{id}", None),
        ("PATCH", "/{id}", {"name": "Changed"}),
        ("DELETE", "/{id}", {}),
    ],
)
def test_inactive_owner_denied_for_every_pet_operation(
    owners, db_session, method, suffix, data
):
    a, _, a_id, _ = owners
    pet = create(a)
    db_session.execute(update(User).where(User.id == a_id).values(is_active=False))
    db_session.flush()
    response = request(a, method, suffix.format(id=pet["id"]), data)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_inactive"
    assert stored(db_session, pet["id"]).name == "Milo"
    assert stored(db_session, pet["id"]).is_active


def test_unverified_active_owner_can_prepare_profile(owners):
    a, *_ = owners
    assert a.get("/me").json()["email_verified_at"] is None
    pet = create(a)
    suffix = "/" + pet["id"]
    assert request(a, "GET").status_code == 200
    assert request(a, "GET", suffix).status_code == 200
    assert request(a, "PATCH", suffix, {"breed": "Mixed"}).status_code == 200
    assert request(a, "DELETE", suffix).status_code == 204


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
@pytest.mark.parametrize("mode", ["missing", "wrong", "other_session"])
def test_every_write_requires_session_bound_csrf(owners, method, mode):
    a, b, *_ = owners
    pet = create(a)
    suffix = "" if method == "POST" else "/" + pet["id"]
    body = (
        {"name": "Intrusion", "species": "CAT"}
        if method == "POST"
        else {"name": "Intrusion"}
        if method == "PATCH"
        else {}
    )
    headers = (
        {}
        if mode == "missing"
        else {"X-CSRF-Token": "x" * 43}
        if mode == "wrong"
        else b.csrf()
    )
    response = request(a, method, suffix, body, csrf=False, headers=headers)
    assert (
        response.status_code == 403
        and response.json()["error"]["code"] == "csrf_failed"
    )
    assert request(a, "GET").json() == [pet]


@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
def test_browser_preflight_allows_required_write_methods(owners, method):
    a, *_ = owners
    response = asyncio.run(
        a.client.options(
            "/api/v1/pets/" + str(uuid4()),
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": (
                    "content-type,x-csrf-token,x-pawtel-request"
                ),
            },
        )
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_create_rolls_back_after_insert_failure(owners, db_session):
    a, *_ = owners

    def fail(mapper, connection, target):
        raise RuntimeError("Synthetic pet insert failure")

    event.listen(Pet, "after_insert", fail)
    try:
        response = request(a, "POST", data={"name": "Milo", "species": "DOG"})
        assert response.status_code == 500
    finally:
        event.remove(Pet, "after_insert", fail)
    assert db_session.scalar(select(Pet)) is None
    assert a.get("/me").status_code == 200
    assert create(a)["name"] == "Milo"


@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
def test_write_rolls_back_after_statement_failure(owners, db_session, method):
    a, *_ = owners
    pet = create(a)
    engine = db_session.get_bind().engine

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.lower().startswith("update pets "):
            raise RuntimeError("Synthetic failure after UPDATE")

    event.listen(engine, "after_cursor_execute", fail)
    try:
        response = request(
            a,
            method,
            "/" + pet["id"],
            {"name": "Intrusion"} if method == "PATCH" else {},
        )
        assert response.status_code == 500
    finally:
        event.remove(engine, "after_cursor_execute", fail)
    assert request(a, "GET", "/" + pet["id"]).json() == pet

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select, update

from app.models import HostProfile, Listing, ListingAcceptedSpecies, Pet, User
from app.services import auth as auth_service
from app.services import listings as listing_service

pytestmark = pytest.mark.integration
LISTING = {
    "title": "Norwood boarding",
    "description": "Synthetic private boarding accommodation.",
    "suburb": "Norwood",
    "state": "SA",
    "postcode": "5067",
    "max_pet_capacity": 3,
    "base_nightly_price_cents": 6500,
    "additional_pet_price_cents": 1500,
    "accepted_species": ["DOG"],
}


def request(api, method, suffix, data=None, *, csrf=True, headers=None):
    metadata = api.csrf() if csrf and method in {"POST", "PATCH", "DELETE"} else {}
    metadata.update(headers or {})
    kwargs = {"headers": metadata}
    if method in {"POST", "PATCH", "DELETE"}:
        kwargs["json"] = {} if data is None else data
    return asyncio.run(api.client.request(method, "/api/v1/host" + suffix, **kwargs))


@pytest.fixture
def account(make_api, db_session, settings):
    def make(email, *, verified=True, host=False):
        api = make_api()
        registration = api.register(email=email)
        assert registration.status_code == 201
        user_id = UUID(registration.json()["user"]["id"])
        if verified:
            with db_session.begin():
                raw = auth_service.issue_verification_token(
                    db_session, user_id, settings
                )
            assert api.post("/verify-email", {"token": raw}).status_code == 204
        assert api.login(email=email).status_code == 200
        if host:
            assert (
                request(
                    api, "POST", "/profile", {"bio": " A boarding host "}
                ).status_code
                == 201
            )
        return api, user_id

    return make


@pytest.fixture
def hosts(account):
    a, a_id = account("host-a@example.com", host=True)
    b, b_id = account("host-b@example.com", host=True)
    return a, b, a_id, b_id


def create(api, **changes):
    response = request(api, "POST", "/listings", {**LISTING, **changes})
    assert response.status_code == 201
    return response.json()


def rows(db, model):
    db.expire_all()
    return db.scalars(select(model)).all()


OPERATIONS = [
    ("GET", "/profile", None),
    ("POST", "/profile", {}),
    ("PATCH", "/profile", {"bio": "Changed"}),
    ("GET", "/listings", None),
    ("POST", "/listings", LISTING),
    ("GET", "/listings/{id}", None),
    ("PATCH", "/listings/{id}", {"title": "Changed"}),
    ("DELETE", "/listings/{id}", {}),
]


@pytest.mark.parametrize("method,path,data", OPERATIONS)
def test_host_management_requires_authentication(make_api, method, path, data):
    response = request(make_api(), method, path.format(id=uuid4()), data, csrf=False)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_unverified_cannot_enable_host_mode(account, db_session):
    api, _ = account("unverified@example.com", verified=False)
    response = request(api, "POST", "/profile")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"
    assert rows(db_session, HostProfile) == []


@pytest.mark.parametrize(
    "state,code",
    [("inactive", "account_inactive"), ("unverified", "email_not_verified")],
)
def test_existing_host_losing_eligibility_cannot_use_any_management_endpoint(
    account, db_session, state, code
):
    api, user_id = account("state@example.com", host=True)
    listing = create(api)
    change = (
        {"is_active": False} if state == "inactive" else {"email_verified_at": None}
    )
    db_session.execute(update(User).where(User.id == user_id).values(change))
    db_session.flush()
    for method, path, data in OPERATIONS:
        response = request(api, method, path.format(id=listing["id"]), data)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == code
    assert rows(db_session, Listing)[0].title == LISTING["title"]
    assert rows(db_session, HostProfile)[0].bio == "A boarding host"


def test_inactive_user_cannot_enable_mode(account, db_session):
    api, user_id = account("disabled@example.com")
    db_session.execute(update(User).where(User.id == user_id).values(is_active=False))
    db_session.flush()
    assert (
        request(api, "POST", "/profile").json()["error"]["code"] == "account_inactive"
    )
    assert rows(db_session, HostProfile) == []


def test_profile_identity_conflict_and_owner_functionality(account, db_session):
    api, user_id = account("dual-purpose@example.com")
    assert (
        request(api, "GET", "/profile").json()["error"]["code"]
        == "host_profile_not_found"
    )
    response = request(api, "POST", "/profile", {"bio": "  My boarding bio  "})
    assert response.status_code == 201
    assert set(response.json()) == {"user_id", "bio", "created_at", "updated_at"}
    assert response.json()["user_id"] == str(user_id)
    assert response.json()["bio"] == "My boarding bio"
    conflict = request(api, "POST", "/profile", {"bio": "Overwrite attempt"})
    assert (
        conflict.status_code == 409
        and conflict.json()["error"]["code"] == "host_profile_exists"
    )
    assert request(api, "GET", "/profile").json()["bio"] == "My boarding bio"
    assert len(rows(db_session, User)) == len(rows(db_session, HostProfile)) == 1
    pet = asyncio.run(
        api.client.post(
            "/api/v1/pets", json={"name": "Milo", "species": "DOG"}, headers=api.csrf()
        )
    )
    assert pet.status_code == 201 and rows(db_session, Pet)[0].owner_id == user_id
    assert api.get("/me").json()["id"] == str(user_id)


@pytest.mark.parametrize(
    "field", ["user_id", "host_id", "owner_id", "id", "created_at"]
)
def test_profile_identity_cannot_be_spoofed(account, field):
    api, _ = account("profile-spoof@example.com")
    response = request(api, "POST", "/profile", {field: str(uuid4())})
    assert response.status_code == 422
    assert request(api, "GET", "/profile").status_code == 404


def test_profile_patch_and_private_singleton(hosts):
    a, b, a_id, b_id = hosts
    assert (
        request(a, "PATCH", "/profile", {"bio": " Changed bio "}).json()["bio"]
        == "Changed bio"
    )
    assert request(b, "GET", "/profile").json()["bio"] == "A boarding host"
    own = request(a, "GET", "/profile?user_id=" + str(b_id)).json()
    assert own["user_id"] == str(a_id) and own["bio"] == "Changed bio"
    assert request(a, "PATCH", "/profile", {"bio": None}).json()["bio"] is None
    assert request(a, "PATCH", "/profile", {"bio": "   "}).json()["bio"] is None
    assert request(a, "PATCH", "/profile", {}).status_code == 422
    assert request(a, "PATCH", "/profile", {"bio": "x" * 2001}).status_code == 422
    assert (
        request(
            a, "PATCH", "/profile", {"user_id": str(b_id), "bio": "Intrusion"}
        ).status_code
        == 422
    )


def test_verified_non_host_requires_mode_before_listing_management(account):
    api, _ = account("not-yet-host@example.com")
    assert request(api, "PATCH", "/profile", {"bio": "No profile"}).status_code == 404
    for method, path, data in OPERATIONS[3:]:
        response = request(api, method, path.format(id=uuid4()), data)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "host_profile_required"


def test_create_listing_is_owned_draft_and_response_is_explicit(hosts, db_session):
    a, _, a_id, _ = hosts
    listing = create(a, title=" Trimmed title ", description=" Description ")
    assert (
        listing["title"] == "Trimmed title" and listing["description"] == "Description"
    )
    assert listing["status"] == "DRAFT" and listing["country_code"] == "AU"
    assert set(listing) == {
        "id",
        "title",
        "description",
        "suburb",
        "state",
        "postcode",
        "country_code",
        "max_pet_capacity",
        "base_nightly_price_cents",
        "additional_pet_price_cents",
        "status",
        "accepted_species",
        "created_at",
        "updated_at",
    }
    row = rows(db_session, Listing)[0]
    assert row.host_id == a_id
    assert rows(db_session, ListingAcceptedSpecies)[0].listing_id == row.id
    response = request(a, "GET", "/listings/" + listing["id"])
    assert (
        response.json() == listing and response.headers["cache-control"] == "no-store"
    )
    for key in [
        "user",
        "host",
        "host_id",
        "password_hash",
        "auth_sessions",
        "email_verified_at",
    ]:
        assert key not in listing


@pytest.mark.parametrize(
    "field", ["host_id", "user_id", "owner_id", "id", "created_at", "status"]
)
def test_create_listing_rejects_server_owned_properties(hosts, db_session, field):
    a, _, _, b_id = hosts
    response = request(
        a,
        "POST",
        "/listings",
        {**LISTING, field: "PUBLISHED" if field == "status" else str(b_id)},
    )
    assert response.status_code == 422 and rows(db_session, Listing) == []


def test_host_collections_are_scoped_ordered_and_status_filtered(hosts):
    a, b, *_ = hosts
    mine = [create(a, title="Zulu"), create(a, title="Alpha")]
    theirs = create(b, title="Private B")
    expected = sorted(mine, key=lambda row: (row["created_at"], row["id"]))
    assert [row["id"] for row in request(a, "GET", "/listings").json()] == [
        row["id"] for row in expected
    ]
    assert [row["id"] for row in request(b, "GET", "/listings").json()] == [
        theirs["id"]
    ]
    assert (
        request(
            a, "PATCH", "/listings/" + mine[0]["id"], {"status": "PUBLISHED"}
        ).status_code
        == 200
    )
    assert [
        row["id"] for row in request(a, "GET", "/listings?status=PUBLISHED").json()
    ] == [mine[0]["id"]]
    assert request(a, "GET", "/listings?status=UNKNOWN").status_code == 422


@pytest.mark.parametrize(
    "method,data", [("GET", None), ("PATCH", {"title": "Intrusion"}), ("DELETE", {})]
)
def test_foreign_and_missing_private_listings_are_indistinguishable(
    hosts, db_session, method, data
):
    a, b, *_ = hosts
    listing = create(a)
    foreign = request(b, method, "/listings/" + listing["id"], data)
    missing = request(b, method, "/listings/" + str(uuid4()), data)
    assert foreign.status_code == missing.status_code == 404
    assert (
        foreign.json()
        == missing.json()
        == {"error": {"code": "listing_not_found", "message": "Listing not found."}}
    )
    assert rows(db_session, Listing)[0].title == LISTING["title"]
    assert rows(db_session, Listing)[0].status.value == "DRAFT"


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_pet_capacity", 0),
        ("max_pet_capacity", -1),
        ("max_pet_capacity", True),
        ("max_pet_capacity", 3.0),
        ("max_pet_capacity", 2147483648),
        ("base_nightly_price_cents", -1),
        ("additional_pet_price_cents", -1),
        ("base_nightly_price_cents", 6500.0),
        ("additional_pet_price_cents", 1.5),
        ("base_nightly_price_cents", "6500"),
        ("additional_pet_price_cents", True),
        ("base_nightly_price_cents", 9007199254740992),
        ("state", "sa"),
        ("state", "UNKNOWN"),
        ("postcode", "123"),
        ("postcode", "12345"),
        ("postcode", "abcd"),
        ("postcode", 5067),
        ("country_code", "NZ"),
        ("title", "  \t "),
        ("title", "x" * 161),
        ("description", " "),
        ("description", "x" * 10001),
        ("suburb", " "),
        ("suburb", "x" * 101),
        ("accepted_species", ["RABBIT"]),
        ("accepted_species", ["dog"]),
        ("accepted_species", ["DOG", "DOG"]),
        ("accepted_species", None),
    ],
)
def test_listing_configuration_validation(hosts, db_session, field, value):
    a, *_ = hosts
    response = request(a, "POST", "/listings", {**LISTING, field: value})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert (
        rows(db_session, Listing) == []
        and rows(db_session, ListingAcceptedSpecies) == []
    )


@pytest.mark.parametrize("species", [["DOG"], ["CAT"], ["DOG", "CAT"]])
def test_supported_species_configurations(hosts, db_session, species):
    a, *_ = hosts
    listing = create(a, accepted_species=species)
    assert listing["accepted_species"] == sorted(species)
    assert len(rows(db_session, ListingAcceptedSpecies)) == len(species)


def test_zero_prices_and_leading_zero_postcode_are_valid_configuration(hosts):
    a, *_ = hosts
    listing = create(
        a,
        state="NT",
        suburb="Darwin",
        postcode="0800",
        base_nightly_price_cents=0,
        additional_pet_price_cents=0,
    )
    assert listing["postcode"] == "0800" and listing["base_nightly_price_cents"] == 0


def test_species_replacement_is_complete_and_invalid_changes_are_atomic(hosts):
    a, *_ = hosts
    listing = create(a)
    path = "/listings/" + listing["id"]
    changed = request(
        a, "PATCH", path, {"title": "Corrected", "accepted_species": ["CAT"]}
    )
    assert changed.status_code == 200 and changed.json()["accepted_species"] == ["CAT"]
    assert changed.json()["max_pet_capacity"] == LISTING["max_pet_capacity"]
    before = request(a, "GET", path).json()
    for species in [["DOG", "DOG"], ["RABBIT"], None]:
        assert (
            request(
                a, "PATCH", path, {"title": "Intrusion", "accepted_species": species}
            ).status_code
            == 422
        )
        assert request(a, "GET", path).json() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("host_id", "other"),
        ("user_id", "other"),
        ("owner_id", "other"),
        ("id", "other"),
        ("created_at", "2020-01-01T00:00:00Z"),
        ("updated_at", "2020-01-01T00:00:00Z"),
    ],
)
def test_listing_patch_rejects_immutable_properties(hosts, field, value):
    a, _, _, b_id = hosts
    listing = create(a)
    response = request(
        a,
        "PATCH",
        "/listings/" + listing["id"],
        {field: str(b_id) if value == "other" else value, "title": "Intrusion"},
    )
    assert response.status_code == 422
    assert request(a, "GET", "/listings/" + listing["id"]).json() == listing


def test_draft_publish_unpublish_and_archive_lifecycle(hosts, db_session):
    a, b, *_ = hosts
    listing = create(a, accepted_species=[])
    path = "/listings/" + listing["id"]
    assert listing["status"] == "DRAFT" and listing["accepted_species"] == []
    failed = request(a, "PATCH", path, {"status": "PUBLISHED", "title": "Not retained"})
    assert (
        failed.status_code == 409
        and failed.json()["error"]["code"] == "listing_not_ready"
    )
    assert request(a, "GET", path).json() == listing
    published = request(
        a, "PATCH", path, {"status": "PUBLISHED", "accepted_species": ["DOG", "CAT"]}
    )
    assert published.status_code == 200 and published.json()["status"] == "PUBLISHED"
    assert (
        request(
            a, "PATCH", path, {"accepted_species": [], "title": "Not retained"}
        ).status_code
        == 409
    )
    assert request(a, "GET", path).json() == published.json()
    assert (
        request(
            a, "PATCH", path, {"status": "DRAFT", "accepted_species": []}
        ).status_code
        == 200
    )
    assert (
        request(
            a, "PATCH", path, {"status": "PUBLISHED", "accepted_species": ["DOG"]}
        ).status_code
        == 200
    )
    assert request(a, "DELETE", path).status_code == 204
    archived = request(a, "GET", path).json()
    assert archived["status"] == "ARCHIVED"
    assert request(a, "GET", "/listings").json() == []
    assert request(a, "GET", "/listings?status=ARCHIVED").json() == [archived]
    assert (
        len(rows(db_session, Listing))
        == len(rows(db_session, ListingAcceptedSpecies))
        == 1
    )
    assert request(a, "DELETE", path).status_code == 204
    assert request(a, "GET", path).json() == archived
    for changes in [{"title": "No edits"}, {"status": "DRAFT"}]:
        response = request(a, "PATCH", path, changes)
        assert (
            response.status_code == 409
            and response.json()["error"]["code"] == "listing_archived"
        )
    assert request(b, "PATCH", path, {"status": "PUBLISHED"}).status_code == 404
    assert request(b, "DELETE", path).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"title": None},
        {"max_pet_capacity": None},
        {"status": "ARCHIVED"},
        {"status": "UNKNOWN"},
    ],
)
def test_empty_null_or_unsupported_status_patch_rejected(hosts, changes):
    a, *_ = hosts
    listing = create(a)
    path = "/listings/" + listing["id"]
    assert request(a, "PATCH", path, changes).status_code == 422
    assert request(a, "GET", path).json() == listing


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_invalid_listing_uuid_uses_safe_validation_error(hosts, method):
    a, *_ = hosts
    response = request(a, method, "/listings/not-a-uuid", {"title": "Changed"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "method,path,data", [operation for operation in OPERATIONS if operation[0] != "GET"]
)
@pytest.mark.parametrize("mode", ["missing", "wrong", "other_session"])
def test_every_host_write_requires_session_csrf(hosts, method, path, data, mode):
    a, b, *_ = hosts
    listing = create(a)
    headers = (
        {}
        if mode == "missing"
        else {"X-CSRF-Token": "x" * 43}
        if mode == "wrong"
        else b.csrf()
    )
    response = request(
        a, method, path.format(id=listing["id"]), data, csrf=False, headers=headers
    )
    assert (
        response.status_code == 403
        and response.json()["error"]["code"] == "csrf_failed"
    )
    assert request(a, "GET", "/listings/" + listing["id"]).json() == listing
    assert request(a, "GET", "/profile").json()["bio"] == "A boarding host"


def test_listing_and_species_creation_roll_back_together(hosts, db_session):
    a, *_ = hosts

    def fail(mapper, connection, target):
        raise RuntimeError("Synthetic species creation failure")

    event.listen(ListingAcceptedSpecies, "before_insert", fail)
    try:
        assert request(a, "POST", "/listings", LISTING).status_code == 500
    finally:
        event.remove(ListingAcceptedSpecies, "before_insert", fail)
    assert (
        rows(db_session, Listing) == []
        and rows(db_session, ListingAcceptedSpecies) == []
    )
    assert request(a, "GET", "/profile").status_code == 200
    assert create(a)["status"] == "DRAFT"


def test_listing_and_species_update_roll_back_together(hosts, monkeypatch):
    a, *_ = hosts
    listing = create(a)
    original = listing_service.replace_species

    def fail(db, listing_id, species):
        original(db, listing_id, species)
        raise RuntimeError("Synthetic failure after species replacement")

    monkeypatch.setattr(listing_service, "replace_species", fail)
    path = "/listings/" + listing["id"]
    response = request(
        a,
        "PATCH",
        path,
        {
            "title": "Not retained",
            "base_nightly_price_cents": 9000,
            "accepted_species": ["CAT"],
        },
    )
    assert response.status_code == 500
    assert request(a, "GET", path).json() == listing

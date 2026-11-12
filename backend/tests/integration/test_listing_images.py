import asyncio
import io
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.errors import APIError
from app.media import service
from app.models import ListingImage
from tests.integration import test_host_api as host_tests
from tests.integration.test_host_api import create, request

# Reuse the existing authenticated fixtures without duplicating setup.
account = host_tests.account
hosts = host_tests.hosts

pytestmark = pytest.mark.integration


class FakeStore:
    fail_upload = False
    fail_delete = False

    def __init__(self):
        self.uploaded = []
        self.deleted = []

    def url(self, public_id):
        return f"https://res.cloudinary.com/synthetic/image/upload/{public_id}"

    def upload(self, content, public_id):
        if self.fail_upload:
            raise APIError(503, "media_provider_failed", "Image provider unavailable.")
        self.uploaded.append(public_id)

    def delete(self, public_id):
        self.deleted.append(public_id)
        return not self.fail_delete


@pytest.fixture
def store(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr("app.api.v1.media.media_store", lambda request: fake)
    return fake


def photo(format="PNG", size=(240, 240)):
    out = io.BytesIO()
    Image.new("RGB", size, "purple").save(out, format=format)
    return out.getvalue()


def upload(api, lid, content=None, mime="image/png", csrf=True):
    headers = api.csrf() if csrf else {}
    headers["Content-Type"] = mime
    return asyncio.run(
        api.client.post(
            f"/api/v1/host/listings/{lid}/images?alt_text=Sunny%20room",
            content=photo() if content is None else content,
            headers=headers,
        )
    )


def test_upload_unauthenticated_rejected(make_api, store):
    assert upload(make_api(), uuid4(), csrf=False).status_code == 401


def test_upload_unverified_rejected(account, store):
    api, _ = account("unverified-media@example.com", verified=False)
    assert upload(api, uuid4()).status_code == 403


def test_upload_nonhost_rejected(account, store):
    api, _ = account("nonhost-media@example.com")
    assert upload(api, uuid4()).json()["error"]["code"] == "host_profile_required"


def test_upload_foreign_and_missing_have_same_404(hosts, store):
    a, b, _, _ = hosts
    listing = create(b)
    for lid in (listing["id"], uuid4()):
        assert upload(a, lid).json()["error"]["code"] == "listing_not_found"
    assert not store.uploaded


def test_upload_requires_csrf_and_request_header(hosts, store):
    api = hosts[0]
    lid = create(api)["id"]
    assert upload(api, lid, csrf=False).json()["error"]["code"] == "csrf_failed"
    headers = api.client.headers.pop("X-PAWTEL-Request")
    assert upload(api, lid).status_code == 403
    api.client.headers["X-PAWTEL-Request"] = headers


@pytest.mark.parametrize(
    "mime,body,status",
    [
        ("image/svg+xml", b"<svg/>", 415),
        ("image/png", b"not a picture", 422),
        ("image/jpeg", photo(), 422),
        ("image/png", b"x" * (service.MAX_BYTES + 1), 413),
        ("image/png", photo(size=(100, 100)), 422),
    ],
)
def test_invalid_upload_rejected(hosts, store, mime, body, status):
    assert upload(hosts[0], create(hosts[0])["id"], body, mime).status_code == status
    assert not store.uploaded


def test_association_order_safe_public_fields_and_removal(hosts, store):
    api = hosts[0]
    lid = create(api)["id"]
    first = upload(api, lid)
    assert first.status_code == 201
    second = upload(api, lid).json()
    assert set(first.json()) == {"id", "url", "alt_text", "sort_order"}
    assert first.json()["sort_order"] == 0 and second["sort_order"] == 1
    order = [second["id"], first.json()["id"]]
    assert (
        request(
            api, "PATCH", f"/listings/{lid}/images/order", {"image_ids": order}
        ).status_code
        == 200
    )
    assert (
        request(api, "PATCH", f"/listings/{lid}", {"status": "PUBLISHED"}).status_code
        == 200
    )
    public = asyncio.run(api.client.get(f"/api/v1/listings/{lid}")).json()
    assert [image["id"] for image in public["images"]] == order
    assert all(
        image["url"].startswith("https://res.cloudinary.com/")
        for image in public["images"]
    )
    assert "public_id" not in str(public) and "api_secret" not in str(public)
    assert request(api, "DELETE", f"/listings/{lid}/images/{second['id']}").json() == {
        "cleanup_pending": False
    }
    assert len(store.deleted) == 1
    assert (
        request(api, "GET", f"/listings/{lid}").json()["images"][0]["id"]
        == first.json()["id"]
    )


def test_six_image_limit_and_reorder_identity_validation(hosts, store):
    api = hosts[0]
    lid = create(api)["id"]
    for _ in range(6):
        assert upload(api, lid).status_code == 201
    assert upload(api, lid).json()["error"]["code"] == "image_limit"
    assert (
        request(
            api, "PATCH", f"/listings/{lid}/images/order", {"image_ids": [str(uuid4())]}
        ).status_code
        == 409
    )


def test_provider_failure_keeps_recoverable_intent_not_public(hosts, store, db_session):
    api = hosts[0]
    lid = create(api)["id"]
    store.fail_upload = True
    assert upload(api, lid).status_code == 503
    assert request(api, "GET", f"/listings/{lid}").json()["images"] == []
    row = db_session.scalar(select(ListingImage))
    ident = row.id
    row.created_at = datetime.now(UTC) - timedelta(minutes=20)
    db_session.commit()
    assert service.cleanup_one(db_session, ident, store, stale_only=True)
    assert db_session.get(ListingImage, ident) is None


def test_db_failure_after_upload_tracks_cleanup_visibly(
    hosts, store, db_session, monkeypatch
):
    api = hosts[0]
    lid = create(api)["id"]
    store.fail_delete = True

    def fail(*args):
        raise SQLAlchemyError("private synthetic database details")

    monkeypatch.setattr(service, "finalize", fail)
    response = upload(api, lid)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "media_association_failed"
    assert "private synthetic" not in response.text
    row = db_session.scalar(select(ListingImage))
    assert row.status == "DELETE_PENDING" and store.uploaded


def test_remove_provider_failure_hides_photo_and_can_retry_cleanup(
    hosts, store, db_session
):
    api = hosts[0]
    lid = create(api)["id"]
    image = upload(api, lid).json()
    store.fail_delete = True
    response = request(api, "DELETE", f"/listings/{lid}/images/{image['id']}")
    assert response.json() == {"cleanup_pending": True}
    assert request(api, "GET", f"/listings/{lid}").json()["images"] == []
    store.fail_delete = False
    assert service.cleanup_one(db_session, UUID(image["id"]), store, stale_only=True)


def test_archived_listing_and_cross_listing_image_operations_rejected(hosts, store):
    a, b, _, _ = hosts
    lid = create(a)["id"]
    image = upload(a, lid).json()
    assert (
        request(b, "DELETE", f"/listings/{lid}/images/{image['id']}").status_code == 404
    )
    assert request(a, "DELETE", f"/listings/{lid}").status_code == 204
    assert upload(a, lid).json()["error"]["code"] == "listing_archived"


def test_cleanup_claim_prevents_a_late_ready_association(hosts, store, db_session):
    api, _, uid, _ = hosts
    lid = UUID(create(api)["id"])
    store.fail_upload = True
    assert upload(api, lid).status_code == 503
    row = db_session.scalar(select(ListingImage))
    ident = row.id
    row.created_at = datetime.now(UTC) - timedelta(minutes=20)
    db_session.commit()

    def delete(public_id):
        with pytest.raises(APIError) as error:
            service.finalize(db_session, uid, lid, ident)
        assert error.value.code == "image_changed"
        return True

    store.delete = delete
    assert service.cleanup_one(db_session, ident, store, stale_only=True)
    assert db_session.get(ListingImage, ident) is None

import io
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import SecretStr

from app.api.errors import APIError
from app.media.provider import CloudinaryStore
from app.media.service import validated_image


@pytest.mark.parametrize(
    "format,mime",
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_common_formats_are_decoded_and_cleanly_reencoded(format, mime):
    original = io.BytesIO()
    Image.new("RGB", (240, 240), "blue").save(original, format=format)
    output = validated_image(original.getvalue() + b"trailing synthetic payload", mime)
    assert b"trailing synthetic payload" not in output
    with Image.open(io.BytesIO(output)) as decoded:
        assert decoded.format == format and decoded.size == (240, 240)


def configured():
    return SimpleNamespace(
        cloudinary_cloud_name="synthetic",
        cloudinary_api_key=SecretStr("synthetic-key"),
        cloudinary_api_secret=SecretStr("synthetic-private-value"),
    )


def test_gateway_uses_fixed_asset_identity_and_server_credentials(monkeypatch):
    calls = []

    def upload(file, **kwargs):
        calls.append(kwargs)
        return {"public_id": kwargs["public_id"], "resource_type": "image"}

    monkeypatch.setattr("cloudinary.uploader.upload", upload)
    store = CloudinaryStore(configured())
    store.upload(b"synthetic", "pawtel/listings/fixed/asset")
    assert calls[0]["overwrite"] is False
    assert calls[0]["allowed_formats"] == ["jpg", "png", "webp"]
    assert store.url("pawtel/listings/fixed/asset").startswith(
        "https://res.cloudinary.com/synthetic/image/upload/"
    )


def test_gateway_sanitizes_provider_failure_and_retries_deletion(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic-private-value")

    monkeypatch.setattr("cloudinary.uploader.upload", fail)
    monkeypatch.setattr("cloudinary.uploader.destroy", fail)
    store = CloudinaryStore(configured())
    with pytest.raises(APIError) as failure:
        store.upload(b"synthetic", "fixed")
    assert "synthetic-private-value" not in failure.value.message
    assert store.delete("fixed") is False


def test_unconfigured_gateway_refuses_before_provider_access():
    settings = configured()
    settings.cloudinary_api_secret = None
    with pytest.raises(APIError) as error:
        CloudinaryStore(settings)
    assert error.value.code == "media_not_configured"


def test_orientation_is_applied_before_stripping_exif():
    content = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (300, 240), "blue").save(content, format="JPEG", exif=exif)
    cleaned = validated_image(content.getvalue(), "image/jpeg")
    with Image.open(io.BytesIO(cleaned)) as result:
        assert result.size == (240, 300)
        assert not result.getexif()

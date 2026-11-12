import io
import logging
import re

import cloudinary.uploader

from app.api.errors import APIError

logging.getLogger("cloudinary").disabled = True


class CloudinaryStore:
    def __init__(self, settings):
        cloud = settings.cloudinary_cloud_name or ""
        key = settings.cloudinary_api_key
        secret = settings.cloudinary_api_secret
        if (
            not re.fullmatch(r"[A-Za-z0-9_-]+", cloud)
            or not key
            or not secret
            or not key.get_secret_value()
            or not secret.get_secret_value()
        ):
            raise APIError(
                503, "media_not_configured", "Image storage is not configured."
            )
        self.cloud = cloud
        self.options = dict(
            cloud_name=cloud,
            api_key=key.get_secret_value(),
            api_secret=secret.get_secret_value(),
            secure=True,
            timeout=20,
        )

    def url(self, public_id):
        return f"https://res.cloudinary.com/{self.cloud}/image/upload/f_auto,q_auto/{public_id}"

    def upload(self, content, public_id):
        try:
            result = cloudinary.uploader.upload(
                io.BytesIO(content),
                public_id=public_id,
                resource_type="image",
                overwrite=False,
                unique_filename=False,
                allowed_formats=["jpg", "png", "webp"],
                **self.options,
            )
            if (
                result.get("public_id") != public_id
                or result.get("resource_type") != "image"
            ):
                raise ValueError("Provider identity mismatch")
        except Exception:
            raise APIError(
                503,
                "media_provider_failed",
                "Image upload could not be completed. "
                "Check your Listing before retrying.",
            ) from None

    def delete(self, public_id):
        try:
            result = cloudinary.uploader.destroy(
                public_id, resource_type="image", invalidate=True, **self.options
            )
            return result.get("result") in {"ok", "not found"}
        except Exception:
            return False

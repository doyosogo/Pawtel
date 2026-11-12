import io
import warnings
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select

from app.api.errors import APIError
from app.models import Listing, ListingImage
from app.schemas.media import ImageOutput
from app.services.host import require_host
from app.services.listings import listing_not_found

MAX_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 6
FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def validated_image(content, mime):
    if mime not in FORMATS:
        raise APIError(415, "invalid_image_type", "Use JPEG, PNG or WebP images.")
    if len(content) > MAX_BYTES:
        raise APIError(413, "image_too_large", "Images must be at most 5 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format != FORMATS[mime] or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Unsupported content")
                width, height = image.size
                if (
                    not (200 <= width <= 6000 and 200 <= height <= 6000)
                    or width * height > 24_000_000
                ):
                    raise ValueError("Invalid dimensions")
                image.load()
                # Re-encoding removes metadata and trailing payloads.
                oriented = ImageOps.exif_transpose(image)
                clean = Image.new(
                    "RGB" if mime == "image/jpeg" else "RGBA", oriented.size
                )
                clean.paste(oriented.convert(clean.mode))
                output = io.BytesIO()
                clean.save(output, format=FORMATS[mime])
                if output.tell() > MAX_BYTES:
                    raise ValueError("Decoded image too large")
                return output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise APIError(
            422,
            "invalid_image",
            "Use a valid, non-animated image, 200–6000 pixels per side "
            "and at most 24 megapixels.",
        ) from None


def owned(db, uid, lid):
    require_host(db, uid)
    listing = db.scalar(
        select(Listing)
        .where(Listing.id == lid, Listing.host_id == uid)
        .with_for_update()
    )
    if listing is None:
        raise listing_not_found()
    if listing.status == "ARCHIVED":
        raise APIError(409, "listing_archived", "Archived Listings are read-only.")
    return listing


def check_owner(db, uid, lid):
    with db.begin():
        owned(db, uid, lid)


def reserve(db, uid, lid, store, alt):
    with db.begin():
        owned(db, uid, lid)
        if (
            db.scalar(
                select(func.count())
                .select_from(ListingImage)
                .where(ListingImage.listing_id == lid)
            )
            >= MAX_IMAGES
        ):
            raise APIError(
                409,
                "image_limit",
                "A Listing supports six images including pending cleanup. "
                "Remove an image or retry after cleanup.",
            )
        ident = uuid4()
        public_id = f"pawtel/listings/{lid}/{ident}"
        row = ListingImage(
            id=ident,
            listing_id=lid,
            public_id=public_id,
            url=store.url(public_id),
            alt_text=alt,
        )
        db.add(row)
        db.flush()
        return ident, public_id


def finalize(db, uid, lid, ident):
    with db.begin():
        owned(db, uid, lid)
        row = db.scalar(
            select(ListingImage)
            .where(ListingImage.id == ident)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None or row.status != "UPLOADING":
            raise APIError(
                409, "image_changed", "Upload has changed. Refresh your Listing."
            )
        maximum = db.scalar(
            select(func.max(ListingImage.sort_order)).where(
                ListingImage.listing_id == lid, ListingImage.status == "READY"
            )
        )
        row.sort_order = (maximum + 1) if maximum is not None else 0
        row.status = "READY"
        db.flush()
        return ImageOutput.model_validate(row)


def cleanup_one(db, ident, store, *, stale_only=False):
    # No provider network operation is performed while a DB lock is held.
    with db.begin():
        lid = db.scalar(select(ListingImage.listing_id).where(ListingImage.id == ident))
        if lid is None:
            return True
        # Same parent-first lock order as finalization/removal. Claim cleanup
        # before the provider call so a concurrent finalizer cannot mark READY.
        db.scalar(select(Listing).where(Listing.id == lid).with_for_update())
        row = db.scalar(
            select(ListingImage)
            .where(ListingImage.id == ident)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None or row.status == "READY":
            return True
        if (
            row.status == "UPLOADING"
            and stale_only
            and row.created_at > datetime.now(UTC) - timedelta(minutes=15)
        ):
            return False
        public_id = row.public_id
        row.status = "DELETE_PENDING"
    if not store.delete(public_id):
        return False
    with db.begin():
        row = db.get(ListingImage, ident)
        if row is not None and row.status != "READY":
            db.delete(row)
    return True


def upload(db, uid, lid, content, mime, alt, store):
    clean = validated_image(content, mime)
    ident, public_id = reserve(db, uid, lid, store, alt)
    try:
        store.upload(clean, public_id)
        return finalize(db, uid, lid, ident)
    except Exception as error:
        db.rollback()
        if isinstance(error, APIError) and error.code == "media_provider_failed":
            # A timed-out upload may still complete remotely. Retain the intent
            # for cleanup after the grace period, rather than dropping its identity.
            raise error from None
        try:
            cleanup_one(db, ident, store)
        except Exception:
            db.rollback()  # Persisted UPLOADING intent remains recoverable by CLI.
        if isinstance(error, APIError):
            raise error from None
        raise APIError(
            503,
            "media_association_failed",
            "Image association failed. Refresh your Listing before retrying; "
            "cleanup is tracked.",
        ) from None


def remove(db, uid, lid, ident, store):
    with db.begin():
        owned(db, uid, lid)
        row = db.scalar(
            select(ListingImage).where(
                ListingImage.id == ident, ListingImage.listing_id == lid
            )
        )
        if row is None:
            raise APIError(404, "image_not_found", "Image not found.")
        row.status = "DELETE_PENDING"
    try:
        cleaned = cleanup_one(db, ident, store)
    except Exception:
        db.rollback()
        cleaned = False
    return {"cleanup_pending": not cleaned}


def reorder(db, uid, lid, ids):
    with db.begin():
        owned(db, uid, lid)
        rows = list(
            db.scalars(
                select(ListingImage).where(
                    ListingImage.listing_id == lid, ListingImage.status == "READY"
                )
            )
        )
        if len(ids) != len(set(ids)) or set(ids) != {row.id for row in rows}:
            raise APIError(
                409, "image_changed", "Images have changed. Refresh before reordering."
            )
        positions = {ident: i for i, ident in enumerate(ids)}
        for row in rows:
            row.sort_order = positions[row.id]
        db.flush()
        return [
            ImageOutput.model_validate(row)
            for row in sorted(rows, key=lambda row: row.sort_order)
        ]

"""Retry tracked deletes/abandoned upload cleanup; never delete READY assets."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_engine
from app.media.provider import CloudinaryStore
from app.media.service import cleanup_one
from app.models import ListingImage


def cleanup():
    store = CloudinaryStore(Settings())
    with Session(get_engine()) as db:
        with db.begin():
            ids = list(
                db.scalars(
                    select(ListingImage.id)
                    .where(
                        or_(
                            ListingImage.status == "DELETE_PENDING",
                            (ListingImage.status == "UPLOADING")
                            & (
                                ListingImage.created_at
                                <= datetime.now(UTC) - timedelta(minutes=15)
                            ),
                        )
                    )
                    .order_by(ListingImage.created_at, ListingImage.id)
                    .limit(100)
                )
            )
        cleaned = 0
        for ident in ids:
            cleaned += cleanup_one(db, ident, store, stale_only=True)
    print(f"Media cleanup complete: {cleaned} tracked assets cleaned.")


def main():
    try:
        cleanup()
    except Exception:
        print("Media cleanup failed. Check storage/database configuration privately.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

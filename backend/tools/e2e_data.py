"""Isolated synthetic E2E setup/teardown. No truncation or development seed reuse."""

import json
import os
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from alembic.config import Config
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.models import (
    AuthSession,
    Booking,
    BookingPet,
    EmailVerificationToken,
    HostProfile,
    Listing,
    ListingAcceptedSpecies,
    ListingImage,
    Pet,
    User,
)
from app.security.credentials import hash_password


def checked_url(value):
    if os.environ.get("APP_ENV") != "test" or not value:
        raise ValueError("E2E requires APP_ENV=test and E2E_DATABASE_URL.")
    url = make_url(value)
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != "pawtel_e2e"
        or url.username != "pawtel_e2e"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.query
    ):
        raise ValueError(
            "E2E requires local pawtel_e2e database/role without URL options."
        )
    return url


def engine_for_e2e():
    engine = create_engine(
        checked_url(os.environ.get("E2E_DATABASE_URL")), hide_parameters=True
    )
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT current_database(), current_user, "
                "current_setting('server_version_num')::int, "
                "(SELECT rolsuper FROM pg_roles WHERE rolname=current_user)"
            )
        ).one()
        if (
            row[:2] != ("pawtel_e2e", "pawtel_e2e")
            or not 180000 <= row[2] < 190000
            or row[3]
        ):
            engine.dispose()
            raise ValueError("Unexpected E2E database/server identity.")
    return engine


def setup(engine):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
    )
    config.attributes["database_url"] = engine.url
    command.upgrade(config, "head")
    run = uuid4().hex
    password = secrets.token_urlsafe(32)
    with Session(engine) as db, db.begin():
        owner = User(
            email=f"owner.{run}@e2e.example.com",
            display_name="E2E Owner",
            password_hash=hash_password(password),
            email_verified_at=datetime.now(UTC),
        )
        host = User(
            email=f"host.{run}@e2e.example.com",
            display_name="E2E Host",
            password_hash=hash_password(password),
            email_verified_at=datetime.now(UTC),
        )
        db.add_all([owner, host])
        db.flush()
        db.add(HostProfile(user_id=host.id, bio="Synthetic E2E Host"))
        db.flush()
        stay = Listing(
            host_id=host.id,
            status="PUBLISHED",
            title=f"E2E garden {run}",
            description="Synthetic isolated E2E accommodation.",
            suburb=f"E2E {run}",
            state="SA",
            postcode="5067",
            country_code="AU",
            max_pet_capacity=2,
            base_nightly_price_cents=5500,
            additional_pet_price_cents=1500,
            accepted_species=[ListingAcceptedSpecies(species="DOG")],
        )
        db.add_all([stay, Pet(owner_id=owner.id, name="E2E Milo", species="DOG")])
        db.flush()
        return {
            "run": run,
            "owner_id": str(owner.id),
            "host_id": str(host.id),
            "owner_email": owner.email,
            "host_email": host.email,
            "password": password,
            "listing_id": str(stay.id),
            "title": stay.title,
            "suburb": stay.suburb,
        }


def cleanup(engine, fixture):
    ids = [UUID(fixture["owner_id"]), UUID(fixture["host_id"])]
    with Session(engine) as db, db.begin():
        users = list(db.scalars(select(User).where(User.id.in_(ids))))
        expected = {fixture["owner_email"], fixture["host_email"]}
        if (
            len(users) != 2
            or {u.email for u in users} != expected
            or any(not u.email.endswith("@e2e.example.com") for u in users)
        ):
            raise ValueError("E2E cleanup identity mismatch; no rows deleted.")
        bids = select(Booking.id).where(Booking.owner_id.in_(ids))
        db.execute(delete(BookingPet).where(BookingPet.booking_id.in_(bids)))
        db.execute(delete(Booking).where(Booking.owner_id.in_(ids)))
        lids = select(Listing.id).where(Listing.host_id.in_(ids))
        # E2E intentionally has no provider uploads. Never orphan cloud assets.
        if db.scalar(
            select(ListingImage.id).where(ListingImage.listing_id.in_(lids)).limit(1)
        ):
            raise ValueError(
                "Unexpected media; preserve fixture for controlled cleanup."
            )
        db.execute(
            delete(ListingAcceptedSpecies).where(
                ListingAcceptedSpecies.listing_id.in_(lids)
            )
        )
        db.execute(delete(Listing).where(Listing.host_id.in_(ids)))
        db.execute(delete(HostProfile).where(HostProfile.user_id.in_(ids)))
        db.execute(delete(Pet).where(Pet.owner_id.in_(ids)))
        db.execute(delete(AuthSession).where(AuthSession.user_id.in_(ids)))
        db.execute(
            delete(EmailVerificationToken).where(
                EmailVerificationToken.user_id.in_(ids)
            )
        )
        db.execute(delete(User).where(User.id.in_(ids)))
        # Foreign dependencies cause transaction rollback, never broader deletion.


def main():
    engine = None
    try:
        engine = engine_for_e2e()
        if sys.argv[1] == "setup":
            path = Path(sys.argv[2])
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as handle:
                json.dump(setup(engine), handle)
            print("Isolated E2E fixtures ready.")
        elif sys.argv[1] == "cleanup":
            cleanup(engine, json.loads(Path(sys.argv[2]).read_text()))
            Path(sys.argv[2]).unlink()
            print("Scoped E2E fixture cleanup complete.")
        else:
            raise ValueError("Unknown E2E command.")
    except Exception:
        print(
            "E2E data operation failed safely. Check the dedicated database privately.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()

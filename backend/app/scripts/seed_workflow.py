"""Opt-in local login identities; not imported by normal registration or routes."""

from datetime import UTC, datetime
from uuid import uuid5

from pydantic import SecretStr
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_engine
from app.models import (
    AuthSession,
    HostProfile,
    Listing,
    ListingAcceptedSpecies,
    Pet,
    User,
)
from app.scripts.seed_demo import NAMESPACE, validate_target
from app.security.credentials import hash_password, verify_password

OWNER_EMAIL = "workflow.owner@pawtel.example.com"
HOST_EMAIL = "workflow.host@pawtel.example.com"
OWNER_ID = uuid5(NAMESPACE, "workflow-owner")
HOST_ID = uuid5(NAMESPACE, "workflow-host")
LISTING_ID = uuid5(NAMESPACE, "workflow-listing")


class DemoSettings(Settings):
    # Only this CLI reads the opt-in password, including from the ignored .env.
    pawtel_demo_password: SecretStr | None = None


def validate_password(password: SecretStr | None):
    if password is None or not 15 <= len(password.get_secret_value()) <= 128:
        raise ValueError(
            "Set PAWTEL_DEMO_PASSWORD to a local 15–128 character passphrase."
        )


def seed_workflow_rows(db: Session, password: SecretStr):
    """Internal writer: entry point must validate target and own the transaction."""
    validate_password(password)
    db.execute(text("SELECT pg_advisory_xact_lock(72719009)"))
    for uid, email, name in (
        (OWNER_ID, OWNER_EMAIL, "Demo Owner"),
        (HOST_ID, HOST_EMAIL, "Demo Host"),
    ):
        user = db.get(User, uid)
        email_owner = db.scalar(select(User.id).where(User.email == email))
        if (user is not None and user.email != email) or (
            email_owner is not None and email_owner != uid
        ):
            raise ValueError("Synthetic identity collision; refusing to overwrite.")
        if user is None:
            user = User(id=uid, email=email, display_name=name)
            db.add(user)
        if not verify_password(password.get_secret_value(), user.password_hash):
            user.password_hash = hash_password(password.get_secret_value())
            # Rotation must not leave existing synthetic login sessions usable.
            db.execute(
                update(AuthSession)
                .where(AuthSession.user_id == uid, AuthSession.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )
        # Explicitly synthetic identities only; normal registration is unchanged.
        user.email_verified_at = user.email_verified_at or datetime.now(UTC)
        db.flush()
    if db.get(HostProfile, HOST_ID) is None:
        db.add(HostProfile(user_id=HOST_ID, bio="Fictional local workflow demo Host."))
        db.flush()
    for slug, name, species in (
        ("dog", "Demo Milo", "DOG"),
        ("cat", "Demo Luna", "CAT"),
    ):
        pid = uuid5(NAMESPACE, "workflow-pet-" + slug)
        pet = db.get(Pet, pid)
        if pet is not None and pet.owner_id != OWNER_ID:
            raise ValueError("Synthetic Pet identity collision; refusing to overwrite.")
        if pet is None:
            db.add(Pet(id=pid, owner_id=OWNER_ID, name=name, species=species))
    listing = db.get(Listing, LISTING_ID)
    if listing is not None and listing.host_id != HOST_ID:
        raise ValueError("Synthetic Listing identity collision; refusing to overwrite.")
    if listing is None:
        db.add(
            Listing(
                id=LISTING_ID,
                host_id=HOST_ID,
                title="Demo workflow garden stay",
                description=(
                    "Fictional local demo accommodation for testing Booking requests."
                ),
                status="PUBLISHED",
                suburb="Norwood",
                state="SA",
                postcode="5067",
                country_code="AU",
                max_pet_capacity=4,
                base_nightly_price_cents=6000,
                additional_pet_price_cents=1500,
                accepted_species=[
                    ListingAcceptedSpecies(species=s) for s in ("DOG", "CAT")
                ],
            )
        )
    db.flush()


def run(settings: DemoSettings):
    validate_target(settings)  # Refuse unsafe environments before any DB work.
    validate_password(settings.pawtel_demo_password)
    with Session(get_engine()) as db, db.begin():
        if tuple(db.execute(text("SELECT current_database(), current_user")).one()) != (
            "pawtel_dev",
            "pawtel_dev",
        ):
            raise ValueError("Unexpected development database identity.")
        if db.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")):
            raise ValueError("Refusing superuser execution.")
        seed_workflow_rows(db, settings.pawtel_demo_password)


def main():
    try:
        run(DemoSettings())
    except Exception:
        # Never echo exception text/connection strings/settings or password inputs.
        print(
            "Workflow seed refused or failed. "
            "Check the local target and demo password configuration."
        )
        raise SystemExit(1) from None
    print(
        "Synthetic Owner/Host workflow ready. "
        "Existing data preserved; no Bookings created."
    )
    print(f"Owner: {OWNER_EMAIL}; Host: {HOST_EMAIL}")
    print("Use the locally configured password. It is never printed by this command.")


if __name__ == "__main__":
    main()

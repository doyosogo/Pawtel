"""Create-only fictional marketplace seed. Never a reset or production data loader."""

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_engine
from app.models import HostProfile, Listing, ListingAcceptedSpecies, User

NAMESPACE = UUID("668b3484-ea6e-480f-922c-438577c820a9")
STAYS = [
    (
        "glenelg",
        "Riley",
        "Glenelg",
        "SA",
        "5045",
        "A sunny home by the coast",
        6200,
        1800,
        3,
        ("DOG", "CAT"),
    ),
    (
        "norwood",
        "Alex",
        "Norwood",
        "SA",
        "5067",
        "A cosy retreat in leafy Norwood",
        5400,
        1500,
        2,
        ("DOG",),
    ),
    (
        "henley",
        "Morgan",
        "Henley Beach",
        "SA",
        "5022",
        "Easy days in a coastal home",
        6800,
        2000,
        3,
        ("DOG", "CAT"),
    ),
    (
        "adelaide",
        "Jamie",
        "Adelaide",
        "SA",
        "5000",
        "A peaceful city hideaway for cats",
        4900,
        1200,
        2,
        ("CAT",),
    ),
    (
        "unley",
        "Taylor",
        "Unley",
        "SA",
        "5061",
        "Warm welcomes in a garden cottage",
        5700,
        1700,
        2,
        ("DOG",),
    ),
    (
        "prospect",
        "Casey",
        "Prospect",
        "SA",
        "5082",
        "A little room to feel at home",
        5900,
        1600,
        4,
        ("DOG", "CAT"),
    ),
    (
        "stirling",
        "Jordan",
        "Stirling",
        "SA",
        "5152",
        "A quiet stay in the Adelaide Hills",
        7200,
        2200,
        3,
        ("DOG", "CAT"),
    ),
    (
        "semaphore",
        "Sam",
        "Semaphore",
        "SA",
        "5019",
        "A gentle seaside stay for cats",
        5100,
        1400,
        2,
        ("CAT",),
    ),
    (
        "sydney",
        "Charlie",
        "Sydney",
        "NSW",
        "2000",
        "A welcoming Sydney home base",
        7800,
        2300,
        2,
        ("DOG", "CAT"),
    ),
    (
        "fitzroy",
        "Frankie",
        "Fitzroy",
        "VIC",
        "3065",
        "A character-filled Melbourne retreat",
        6500,
        1900,
        2,
        ("DOG",),
    ),
    (
        "brisbane",
        "Avery",
        "Brisbane",
        "QLD",
        "4000",
        "Sunny company in a relaxed home",
        5800,
        1700,
        3,
        ("DOG", "CAT"),
    ),
    (
        "fremantle",
        "Quinn",
        "Fremantle",
        "WA",
        "6160",
        "A calm corner of the west coast",
        6100,
        1600,
        2,
        ("DOG", "CAT"),
    ),
]


def validate_target(settings: Settings):
    if settings.app_env != "development" or not settings.database_url:
        raise ValueError(
            "Demo seed requires APP_ENV=development and a local development URL."
        )
    url = make_url(str(settings.database_url))
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != "pawtel_dev"
        or url.username != "pawtel_dev"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.query
    ):
        raise ValueError(
            "Demo seed requires local pawtel_dev database/role without URL options."
        )
    return url


def seed_rows(db: Session):
    """Internal create-only writer; caller must validate target and own transaction."""
    db.execute(text("SELECT pg_advisory_xact_lock(72719009)"))
    created = 0
    for (
        slug,
        name,
        suburb,
        state,
        postcode,
        title,
        base,
        extra,
        capacity,
        species,
    ) in STAYS:
        uid = uuid5(NAMESPACE, "host-" + slug)
        lid = uuid5(NAMESPACE, "listing-" + slug)
        email = f"seed.{slug}@demo.pawtel.test"
        user = db.get(User, uid)
        if user is not None and user.email != email:
            raise ValueError("Seed identity collision; refusing to overwrite.")
        if user is None:
            user = User(
                id=uid,
                email=email,
                display_name=name,
                email_verified_at=datetime.now(UTC),
                password_hash=None,
            )
            db.add(user)
            db.flush()
        if db.get(HostProfile, uid) is None:
            db.add(
                HostProfile(
                    user_id=uid,
                    bio=(
                        f"Hi, I’m {name}. "
                        "I enjoy making visiting pets feel settled and welcome. "
                        f"My home in {suburb} is a place for quiet company "
                        "and an easy routine. "
                        "This is a fictional PAWTEL demo host."
                    ),
                )
            )
            db.flush()
        listing = db.get(Listing, lid)
        if listing is not None:
            if listing.host_id != uid:
                raise ValueError(
                    "Seed Listing identity collision; refusing to overwrite."
                )
            continue
        db.add(
            Listing(
                id=lid,
                host_id=uid,
                status="PUBLISHED",
                title=title,
                description=(
                    f"A thoughtful boarding stay in {suburb}, "
                    "with time to settle in and feel at home. "
                    "Your companion can enjoy a familiar daily rhythm, "
                    "a comfortable place to rest "
                    "and plenty of gentle company.\n\n"
                    "We would discuss your pet’s routine before any stay. "
                    "This accommodation and "
                    "its host are fictional examples created for "
                    "the PAWTEL portfolio demo."
                ),
                suburb=suburb,
                state=state,
                postcode=postcode,
                country_code="AU",
                max_pet_capacity=capacity,
                base_nightly_price_cents=base,
                additional_pet_price_cents=extra,
                accepted_species=[
                    ListingAcceptedSpecies(species=item) for item in species
                ],
            )
        )
        db.flush()
        created += 1
    return created


def main():
    settings = Settings()
    validate_target(settings)
    with Session(get_engine()) as db, db.begin():
        identity = db.execute(text("SELECT current_database(), current_user")).one()
        if tuple(identity) != ("pawtel_dev", "pawtel_dev"):
            raise ValueError("Connected target differs from safe development identity.")
        if db.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")):
            raise ValueError("Refusing to seed as a superuser.")
        count = seed_rows(db)
    print(f"Demo seed complete: {count} Listings created; existing rows preserved.")
    print(
        "All hosts/stays are fictional. "
        "Seed accounts have no passwords or login access."
    )


if __name__ == "__main__":
    main()

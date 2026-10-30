from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, joinedload

from app.api.errors import APIError
from app.models import Listing, ListingAcceptedSpecies
from app.models.enums import ListingStatus, PetSpecies
from app.schemas.host import ListingCreate, ListingPatch
from app.services.host import require_host


def listing_not_found() -> APIError:
    return APIError(404, "listing_not_found", "Listing not found.")


def owned_listing(db: Session, host_id: UUID, listing_id: UUID) -> Listing:
    # One joined statement provides a consistent parent/species snapshot and avoids N+1.
    listing = (
        db.execute(
            select(Listing)
            .where(Listing.id == listing_id, Listing.host_id == host_id)
            .options(joinedload(Listing.accepted_species))
            .execution_options(populate_existing=True)
        )
        .unique()
        .scalar_one_or_none()
    )
    if listing is None:
        raise listing_not_found()
    return listing


def create_listing(db: Session, user_id: UUID, data: ListingCreate) -> Listing:
    values = data.model_dump(exclude={"accepted_species"})
    with db.begin():
        host = require_host(db, user_id)
        listing = Listing(host_id=host.user_id, status=ListingStatus.DRAFT, **values)
        listing.accepted_species = [
            ListingAcceptedSpecies(species=species) for species in data.accepted_species
        ]
        db.add(listing)
        db.flush()
        result = owned_listing(db, host.user_id, listing.id)
    return result


def list_listings(
    db: Session, user_id: UUID, status: ListingStatus | None = None
) -> list[Listing]:
    with db.begin():
        host = require_host(db, user_id)
        query = select(Listing).where(Listing.host_id == host.user_id)
        query = (
            query.where(Listing.status != ListingStatus.ARCHIVED)
            if status is None
            else query.where(Listing.status == status)
        )
        result = list(
            db.execute(
                query.options(joinedload(Listing.accepted_species)).order_by(
                    Listing.created_at, Listing.id
                )
            )
            .unique()
            .scalars()
        )
    return result


def get_listing(db: Session, user_id: UUID, listing_id: UUID) -> Listing:
    with db.begin():
        host = require_host(db, user_id)
        listing = owned_listing(db, host.user_id, listing_id)
    return listing


def replace_species(db: Session, listing_id: UUID, species: list[PetSpecies]) -> None:
    """Internal helper; caller owns transaction and has already written owned parent."""
    db.execute(
        delete(ListingAcceptedSpecies).where(
            ListingAcceptedSpecies.listing_id == listing_id
        )
    )
    db.add_all(
        [
            ListingAcceptedSpecies(listing_id=listing_id, species=item)
            for item in species
        ]
    )
    db.flush()


def update_listing(
    db: Session, user_id: UUID, listing_id: UUID, data: ListingPatch
) -> Listing:
    changes = data.model_dump(exclude_unset=True, exclude={"accepted_species"})
    with db.begin():
        host = require_host(db, user_id)
        # An ordinary parent UPDATE precedes all species work, even for species-only
        # edits. Its inherent row write lock serialises related replacement/validation
        # until commit, without an explicit booking-style SELECT FOR UPDATE protocol.
        listing = db.scalar(
            update(Listing)
            .where(
                Listing.id == listing_id,
                Listing.host_id == host.user_id,
                Listing.status != ListingStatus.ARCHIVED,
            )
            .values(**changes, updated_at=func.now())
            .returning(Listing)
        )
        if listing is None:
            owned_status = db.scalar(
                select(Listing.status).where(
                    Listing.id == listing_id, Listing.host_id == host.user_id
                )
            )
            if owned_status is None:
                raise listing_not_found()
            raise APIError(
                409,
                "listing_archived",
                "Archived listings cannot be edited or restored.",
            )
        species = (
            data.accepted_species
            if "accepted_species" in data.model_fields_set
            else list(
                db.scalars(
                    select(ListingAcceptedSpecies.species).where(
                        ListingAcceptedSpecies.listing_id == listing_id
                    )
                )
            )
        )
        if listing.status == ListingStatus.PUBLISHED and not species:
            raise APIError(
                409,
                "listing_not_ready",
                "A published listing must accept at least one pet species.",
            )
        if "accepted_species" in data.model_fields_set:
            replace_species(db, listing.id, species)
        result = owned_listing(db, host.user_id, listing.id)
    return result


def archive_listing(db: Session, user_id: UUID, listing_id: UUID) -> None:
    with db.begin():
        host = require_host(db, user_id)
        changed_id = db.scalar(
            update(Listing)
            .where(
                Listing.id == listing_id,
                Listing.host_id == host.user_id,
                Listing.status != ListingStatus.ARCHIVED,
            )
            .values(status=ListingStatus.ARCHIVED)
            .returning(Listing.id)
        )
        if (
            changed_id is None
            and db.scalar(
                select(Listing.id).where(
                    Listing.id == listing_id, Listing.host_id == host.user_id
                )
            )
            is None
        ):
            raise listing_not_found()

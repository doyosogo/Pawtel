from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.models import Pet
from app.schemas.pets import PetCreate, PetPatch


def pet_not_found() -> APIError:
    # Neither a global lookup nor a separate not-owner response is needed.
    return APIError(404, "pet_not_found", "Pet not found.")


def create_pet(db: Session, owner_id: UUID, data: PetCreate) -> Pet:
    with db.begin():
        pet = Pet(owner_id=owner_id, **data.model_dump())
        db.add(pet)
        db.flush()
    return pet


def list_pets(
    db: Session, owner_id: UUID, *, include_archived: bool = False
) -> list[Pet]:
    query = select(Pet).where(Pet.owner_id == owner_id)
    if not include_archived:
        query = query.where(Pet.is_active.is_(True))
    with db.begin():
        return list(db.scalars(query.order_by(Pet.created_at, Pet.id)))


def get_pet(db: Session, owner_id: UUID, pet_id: UUID) -> Pet:
    with db.begin():
        pet = db.scalar(select(Pet).where(Pet.id == pet_id, Pet.owner_id == owner_id))
        if pet is None:
            raise pet_not_found()
    return pet


def update_pet(db: Session, owner_id: UUID, pet_id: UUID, data: PetPatch) -> Pet:
    with db.begin():
        # Owner filtering is in the actual write as well as the read endpoints.
        # Only explicitly supplied editable fields are written, never stale copies
        # of omitted fields or ownership/archive state.
        pet = db.scalar(
            update(Pet)
            .where(Pet.id == pet_id, Pet.owner_id == owner_id)
            .values(**data.model_dump(exclude_unset=True))
            .returning(Pet)
        )
        if pet is None:
            raise pet_not_found()
    return pet


def archive_pet(db: Session, owner_id: UUID, pet_id: UUID) -> None:
    with db.begin():
        archived_id = db.scalar(
            update(Pet)
            .where(Pet.id == pet_id, Pet.owner_id == owner_id, Pet.is_active.is_(True))
            .values(is_active=False)
            .returning(Pet.id)
        )
        if archived_id is None:
            # Already archived is idempotent, but missing/foreign stays private.
            owned_id = db.scalar(
                select(Pet.id).where(Pet.id == pet_id, Pet.owner_id == owner_id)
            )
            if owned_id is None:
                raise pet_not_found()

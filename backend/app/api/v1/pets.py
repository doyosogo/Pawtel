from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.models import User
from app.schemas.pets import PetCreate, PetOutput, PetPatch
from app.security.dependencies import (
    Database,
    active_user,
    csrf_for_authenticated_requests,
)
from app.services import pets as service

Owner = Annotated[User, Depends(active_user)]
router = APIRouter(
    prefix="/api/v1/pets",
    tags=["pets"],
    dependencies=[Depends(active_user), Depends(csrf_for_authenticated_requests)],
)


@router.post("", status_code=201, response_model=PetOutput)
def create_pet(body: PetCreate, db: Database, owner: Owner):
    return PetOutput.model_validate(service.create_pet(db, owner.id, body))


@router.get("", response_model=list[PetOutput])
def list_pets(db: Database, owner: Owner, include_archived: bool = False):
    return [
        PetOutput.model_validate(pet)
        for pet in service.list_pets(db, owner.id, include_archived=include_archived)
    ]


@router.get("/{pet_id}", response_model=PetOutput)
def get_pet(pet_id: UUID, db: Database, owner: Owner):
    return PetOutput.model_validate(service.get_pet(db, owner.id, pet_id))


@router.patch("/{pet_id}", response_model=PetOutput)
def update_pet(pet_id: UUID, body: PetPatch, db: Database, owner: Owner):
    return PetOutput.model_validate(service.update_pet(db, owner.id, pet_id, body))


@router.delete("/{pet_id}", status_code=204)
def archive_pet(pet_id: UUID, db: Database, owner: Owner):
    service.archive_pet(db, owner.id, pet_id)
    return Response(status_code=204)

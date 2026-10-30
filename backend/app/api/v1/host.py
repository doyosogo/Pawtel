from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.models import User
from app.models.enums import ListingStatus
from app.schemas.host import (
    HostEnable,
    HostOutput,
    HostPatch,
    ListingCreate,
    ListingOutput,
    ListingPatch,
)
from app.security.dependencies import (
    Database,
    csrf_for_authenticated_requests,
    verified_user,
)
from app.services import host as host_service
from app.services import listings as listing_service

VerifiedUser = Annotated[User, Depends(verified_user)]
router = APIRouter(
    prefix="/api/v1/host",
    tags=["private host management"],
    dependencies=[Depends(verified_user), Depends(csrf_for_authenticated_requests)],
)


@router.get("/profile", response_model=HostOutput)
def get_profile(db: Database, user: VerifiedUser):
    return HostOutput.model_validate(host_service.get_profile(db, user.id))


@router.post("/profile", status_code=201, response_model=HostOutput)
def enable_host(body: HostEnable, db: Database, user: VerifiedUser):
    return HostOutput.model_validate(host_service.enable_host(db, user.id, body))


@router.patch("/profile", response_model=HostOutput)
def update_profile(body: HostPatch, db: Database, user: VerifiedUser):
    return HostOutput.model_validate(host_service.update_profile(db, user.id, body))


@router.post("/listings", status_code=201, response_model=ListingOutput)
def create_listing(body: ListingCreate, db: Database, user: VerifiedUser):
    return ListingOutput.from_listing(listing_service.create_listing(db, user.id, body))


@router.get("/listings", response_model=list[ListingOutput])
def list_listings(
    db: Database, user: VerifiedUser, status: ListingStatus | None = None
):
    return [
        ListingOutput.from_listing(row)
        for row in listing_service.list_listings(db, user.id, status)
    ]


@router.get("/listings/{listing_id}", response_model=ListingOutput)
def get_listing(listing_id: UUID, db: Database, user: VerifiedUser):
    return ListingOutput.from_listing(
        listing_service.get_listing(db, user.id, listing_id)
    )


@router.patch("/listings/{listing_id}", response_model=ListingOutput)
def update_listing(
    listing_id: UUID, body: ListingPatch, db: Database, user: VerifiedUser
):
    return ListingOutput.from_listing(
        listing_service.update_listing(db, user.id, listing_id, body)
    )


@router.delete("/listings/{listing_id}", status_code=204)
def archive_listing(listing_id: UUID, db: Database, user: VerifiedUser):
    listing_service.archive_listing(db, user.id, listing_id)
    return Response(status_code=204)

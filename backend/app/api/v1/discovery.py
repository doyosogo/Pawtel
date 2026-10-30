from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.schemas.discovery import (
    Availability,
    ListingPage,
    PublicListing,
    SearchQuery,
    StayQuery,
)
from app.security.dependencies import Database
from app.services import discovery

router = APIRouter(prefix="/api/v1/listings", tags=["public listings"])


@router.get("", response_model=ListingPage)
def search(db: Database, filters: Annotated[SearchQuery, Query()]):
    return discovery.search(db, filters)


@router.get("/{listing_id}", response_model=PublicListing)
def detail(listing_id: UUID, db: Database):
    return discovery.detail(db, listing_id)


@router.get("/{listing_id}/availability", response_model=Availability)
def availability(listing_id: UUID, db: Database, stay: Annotated[StayQuery, Query()]):
    return discovery.availability(db, listing_id, stay)

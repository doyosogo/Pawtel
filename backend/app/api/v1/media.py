from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from starlette.concurrency import run_in_threadpool

from app.api.errors import APIError
from app.media import service
from app.media.provider import CloudinaryStore
from app.models import User
from app.schemas.media import ImageOrder, ImageOutput
from app.security.dependencies import (
    Database,
    csrf_for_authenticated_requests,
    request_settings,
    verified_user,
)

router = APIRouter(
    prefix="/api/v1/host/listings",
    dependencies=[Depends(verified_user), Depends(csrf_for_authenticated_requests)],
)
UserDep = Annotated[User, Depends(verified_user)]


def media_store(request: Request):
    return CloudinaryStore(request_settings(request))


@router.post("/{listing_id}/images", response_model=ImageOutput, status_code=201)
async def upload(
    listing_id: UUID,
    request: Request,
    db: Database,
    user: UserDep,
    alt_text: str = Query("", max_length=160),
):
    await run_in_threadpool(service.check_owner, db, user.id, listing_id)
    mime = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if mime not in service.FORMATS:
        raise APIError(415, "invalid_image_type", "Use JPEG, PNG or WebP.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > service.MAX_BYTES:
            raise APIError(413, "image_too_large", "Images must be at most 5 MiB.")
        body.extend(chunk)
    store = media_store(request)
    return await run_in_threadpool(
        service.upload,
        db,
        user.id,
        listing_id,
        bytes(body),
        mime,
        alt_text.strip(),
        store,
    )


@router.patch("/{listing_id}/images/order", response_model=list[ImageOutput])
def order(listing_id: UUID, body: ImageOrder, db: Database, user: UserDep):
    return service.reorder(db, user.id, listing_id, body.image_ids)


@router.delete("/{listing_id}/images/{image_id}")
def remove(
    listing_id: UUID, image_id: UUID, request: Request, db: Database, user: UserDep
):
    service.check_owner(db, user.id, listing_id)
    return service.remove(db, user.id, listing_id, image_id, media_store(request))

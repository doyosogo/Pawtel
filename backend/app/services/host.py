from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.models import HostProfile
from app.schemas.host import HostEnable, HostPatch


def profile_not_found() -> APIError:
    return APIError(404, "host_profile_not_found", "Host mode is not enabled.")


def require_host(db: Session, user_id: UUID) -> HostProfile:
    """Resolve only this caller's profile within the calling service transaction."""
    profile = db.scalar(select(HostProfile).where(HostProfile.user_id == user_id))
    if profile is None:
        raise APIError(
            403, "host_profile_required", "Enable Host mode before managing listings."
        )
    return profile


def get_profile(db: Session, user_id: UUID) -> HostProfile:
    with db.begin():
        profile = db.scalar(select(HostProfile).where(HostProfile.user_id == user_id))
        if profile is None:
            raise profile_not_found()
    return profile


def enable_host(db: Session, user_id: UUID, data: HostEnable) -> HostProfile:
    with db.begin():
        # The shared PK, not a pre-insert existence check, arbitrates competing enables.
        profile = db.scalar(
            insert(HostProfile)
            .values(user_id=user_id, bio=data.bio)
            .on_conflict_do_nothing(index_elements=[HostProfile.user_id])
            .returning(HostProfile)
        )
        if profile is None:
            raise APIError(409, "host_profile_exists", "Host mode is already enabled.")
    return profile


def update_profile(db: Session, user_id: UUID, data: HostPatch) -> HostProfile:
    with db.begin():
        profile = db.scalar(
            update(HostProfile)
            .where(HostProfile.user_id == user_id)
            .values(**data.model_dump(exclude_unset=True))
            .returning(HostProfile)
        )
        if profile is None:
            raise profile_not_found()
    return profile

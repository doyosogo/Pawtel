import hmac
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.core.config import Settings
from app.db.session import get_session
from app.models import AuthSession, User
from app.security.credentials import token_digest, valid_token

Database = Annotated[Session, Depends(get_session)]


def request_settings(request: Request) -> Settings:
    return request.app.state.settings


@dataclass
class AuthContext:
    session: AuthSession = field(repr=False)
    user: User


def optional_auth(request: Request, db: Database) -> AuthContext | None:
    settings = request_settings(request)
    raw = request.cookies.get(settings.session_cookie_name, "")
    if not valid_token(raw):
        return None
    with db.begin():
        row = db.execute(
            select(AuthSession, User)
            .join(User)
            .where(
                AuthSession.token_digest == token_digest(raw, "session"),
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(UTC),
            )
        ).one_or_none()
    return AuthContext(*row) if row else None


OptionalAuth = Annotated[AuthContext | None, Depends(optional_auth)]


def required_user(context: OptionalAuth) -> User:
    if context is None:
        raise APIError(401, "authentication_required", "Authentication is required.")
    return context.user


def active_user(user: Annotated[User, Depends(required_user)]) -> User:
    if not user.is_active:
        raise APIError(403, "account_inactive", "This account is inactive.")
    return user


def verified_user(user: Annotated[User, Depends(active_user)]) -> User:
    if user.email_verified_at is None:
        raise APIError(403, "email_not_verified", "Verified email is required.")
    return user


def csrf_for_authenticated_requests(request: Request, context: OptionalAuth) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"} or context is None:
        return
    supplied = request.headers.get("x-csrf-token", "")
    if not valid_token(supplied) or not hmac.compare_digest(
        supplied, context.session.csrf_token
    ):
        raise APIError(403, "csrf_failed", "A valid CSRF token is required.")

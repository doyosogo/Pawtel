from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.core.config import Settings
from app.models import AuthSession, EmailVerificationToken, User
from app.security.credentials import (
    PASSWORD_HASHER,
    hash_password,
    new_token,
    token_digest,
    valid_token,
    verify_password,
)


@dataclass
class RegistrationResult:
    user: User
    # Ephemeral delivery boundary for a future email adapter; never an API field.
    verification_token: str = field(repr=False)


@dataclass
class LoginResult:
    user: User
    expires_at: datetime
    session_token: str = field(repr=False)


def invalid_credentials() -> APIError:
    return APIError(401, "invalid_credentials", "Email or password is incorrect.")


def invalid_verification() -> APIError:
    return APIError(
        400,
        "verification_invalid",
        "Verification token is invalid or no longer usable.",
    )


def issue_verification_token(db: Session, user_id: UUID, settings: Settings) -> str:
    """Caller owns transaction; serialise replacements/consumption via User lock.

    This helper does not send email. The raw value exists only for a delivery
    caller/test; replacement deletes the previous row, including consumed history.
    """
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or not user.is_active or user.email_verified_at is not None:
        raise invalid_verification()
    db.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
    )
    raw = new_token()
    db.add(
        EmailVerificationToken(
            user_id=user_id,
            email=user.email,
            token_digest=token_digest(raw, "verification"),
            expires_at=datetime.now(UTC)
            + timedelta(seconds=settings.verification_lifetime_seconds),
        )
    )
    db.flush()
    return raw


def register(
    db: Session, *, email: str, display_name: str, password: str, settings: Settings
) -> RegistrationResult:
    encoded = hash_password(password)  # Expensive work before opening a transaction.
    try:
        with db.begin():
            user = User(email=email, display_name=display_name, password_hash=encoded)
            db.add(user)
            db.flush()
            raw = issue_verification_token(db, user.id, settings)
    except IntegrityError as error:
        if error.orig.diag.constraint_name == "uq_users_email":
            raise APIError(
                409,
                "registration_unavailable",
                "Unable to register with these details.",
            ) from None
        raise
    return RegistrationResult(user, raw)


def login(
    db: Session,
    *,
    email: str,
    password: str,
    settings: Settings,
    current_session_id: UUID | None = None,
) -> LoginResult:
    with db.begin():
        user = db.scalar(select(User).where(User.email == email))
        user_id = user.id if user else None
        encoded = user.password_hash if user else None
    # Missing email and legacy NULL hashes do not skip expensive verification.
    valid = verify_password(password, encoded)
    if not valid or user_id is None:
        raise invalid_credentials()
    replacement = (
        hash_password(password) if PASSWORD_HASHER.check_needs_rehash(encoded) else None
    )
    raw = new_token()
    with db.begin():
        user = db.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None or not user.is_active or user.password_hash != encoded:
            raise invalid_credentials()
        if replacement:
            user.password_hash = replacement
        now = datetime.now(UTC)
        if current_session_id is not None:
            db.execute(
                update(AuthSession)
                .where(
                    AuthSession.id == current_session_id,
                    AuthSession.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
        expires_at = now + timedelta(seconds=settings.session_lifetime_seconds)
        db.add(
            AuthSession(
                user_id=user.id,
                token_digest=token_digest(raw, "session"),
                csrf_token=new_token(),
                expires_at=expires_at,
            )
        )
        db.flush()
    return LoginResult(user, expires_at, raw)


def logout(db: Session, session_id: UUID | None) -> None:
    if session_id is None:
        return
    with db.begin():
        db.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )


def verify_email(db: Session, raw: str) -> None:
    if not valid_token(raw):
        raise invalid_verification()
    digest = token_digest(raw, "verification")
    with db.begin():
        user_id = db.scalar(
            select(EmailVerificationToken.user_id).where(
                EmailVerificationToken.token_digest == digest
            )
        )
        if user_id is None:
            raise invalid_verification()
        # Same lock order as token replacement. Re-read token after the lock wait.
        user = db.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        token = db.scalar(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.token_digest == digest)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        now = datetime.now(UTC)
        if (
            user is None
            or not user.is_active
            or user.email_verified_at is not None
            or token is None
            or token.email != user.email
            or token.consumed_at is not None
            or token.expires_at <= now
        ):
            raise invalid_verification()
        token.consumed_at = now
        user.email_verified_at = now
        db.flush()

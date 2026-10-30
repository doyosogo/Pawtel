from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.models import User
from app.schemas.auth import (
    CSRFOutput,
    LoginInput,
    RegisterInput,
    RegistrationOutput,
    UserSelf,
    VerificationInput,
)
from app.security.dependencies import (
    Database,
    OptionalAuth,
    active_user,
    csrf_for_authenticated_requests,
    request_settings,
    required_user,
)
from app.services import auth as service

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["authentication"],
    dependencies=[Depends(csrf_for_authenticated_requests)],
)


@router.post("/register", status_code=201, response_model=RegistrationOutput)
def register(body: RegisterInput, request: Request, db: Database):
    result = service.register(
        db,
        email=body.email,
        display_name=body.display_name,
        password=body.password.get_secret_value(),
        settings=request_settings(request),
    )
    # No provider exists. Do not return/log the ephemeral raw delivery token.
    return RegistrationOutput(user=UserSelf.model_validate(result.user))


@router.post("/login", response_model=UserSelf)
def login(
    body: LoginInput,
    request: Request,
    response: Response,
    db: Database,
    context: OptionalAuth,
):
    settings = request_settings(request)
    result = service.login(
        db,
        email=body.email,
        password=body.password.get_secret_value(),
        settings=settings,
        current_session_id=context.session.id if context else None,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.session_token,
        max_age=settings.session_lifetime_seconds,
        expires=result.expires_at,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return UserSelf.model_validate(result.user)


@router.post("/logout", status_code=204)
def logout(request: Request, db: Database, context: OptionalAuth):
    service.logout(db, context.session.id if context else None)
    settings = request_settings(request)
    response = Response(status_code=204)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/me", response_model=UserSelf)
def me(user: Annotated[User, Depends(active_user)]):
    return user


@router.get("/csrf", response_model=CSRFOutput)
def csrf(context: OptionalAuth, user: Annotated[User, Depends(required_user)]):
    return CSRFOutput(csrf_token=context.session.csrf_token)


@router.post("/verify-email", status_code=204)
def verify_email(body: VerificationInput, db: Database):
    service.verify_email(db, body.token.get_secret_value())
    return Response(status_code=204)

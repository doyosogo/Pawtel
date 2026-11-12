"""Operator-only synthetic account setup/rotation, never an HTTP reset endpoint."""

import os

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import User
from app.scripts.seed_workflow import (
    HOST_ID,
    OWNER_ID,
    DemoSettings,
    seed_workflow_rows,
    validate_password,
)


def validate_target(settings):
    if (
        settings.app_env != "production"
        or not settings.portfolio_demo
        or os.environ.get("PORTFOLIO_SEED_CONFIRM") != "pawtel_portfolio"
    ):
        raise ValueError("Explicit dedicated portfolio target confirmation required.")
    url = make_url(str(settings.database_url))
    if (
        url.database != "pawtel_portfolio"
        or url.username != "pawtel_portfolio"
        or url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}
    ):
        raise ValueError("Dedicated TLS portfolio database and role required.")
    validate_password(settings.pawtel_demo_password)


def seed_rows(db, password):
    # Even a mislabelled database containing unrelated identities is never modified.
    if db.scalar(select(User.id).where(User.id.not_in([OWNER_ID, HOST_ID])).limit(1)):
        raise ValueError("Unrelated identities present; refusing portfolio seed.")
    seed_workflow_rows(db, password)


def run(settings):
    validate_target(settings)
    with Session(get_engine()) as db, db.begin():
        if tuple(db.execute(text("SELECT current_database(), current_user")).one()) != (
            "pawtel_portfolio",
            "pawtel_portfolio",
        ):
            raise ValueError("Unexpected database identity.")
        if db.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")):
            raise ValueError("Superuser refused.")
        seed_rows(db, settings.pawtel_demo_password)


def main():
    try:
        run(DemoSettings())
    except Exception:
        print(
            "Portfolio seed refused or failed. Check target and private configuration."
        )
        raise SystemExit(1) from None
    print(
        "Synthetic portfolio accounts ready. No Bookings created; password not printed."
    )


if __name__ == "__main__":
    main()

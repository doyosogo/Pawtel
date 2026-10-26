# Architecture

```text
React + TypeScript
        ↓ (future domain API calls)
FastAPI REST API
        ↓
SQLAlchemy 2
        ↓
PostgreSQL 18
```

## Implemented boundaries

The independently runnable frontend uses Vite, Tailwind, React Router and a TanStack
Query provider. Zustand is installed for future client state. src/app composes
providers/routing, src/pages holds the temporary screen and src/test owns test setup.
No marketplace UI or domain API calls have been built. Future features can live
under src/features when real requirements exist.

FastAPI app/main.py owns lifespan/CORS and exposes only /health beyond framework
documentation. app/core reads root .env and environment overrides. app/db owns named
metadata, a lazy engine and per-operation sessions. Startup and health do not create
an engine or require PostgreSQL. Sessions clean up resources but future services
must explicitly own transaction boundaries.

app/models contains typed account, pet, listing and booking persistence models, with
common UUID/timestamp mixins and native enum declarations. An explicit registry in
app/models/__init__.py imports every model; Alembic imports it for complete metadata.
TYPE_CHECKING imports and SQLAlchemy forward relationships avoid runtime model
import cycles. These are database models, not Pydantic API schemas. Models are not
exposed through CRUD/booking/authentication endpoints.

Alembic owns schema creation and versioning. The initial migration is independent
of mutable model definitions and owns native enum creation/removal. There is no
startup create_all. Real PostgreSQL integration tests use these migrations, a
separate protected test database and rollback/savepoint isolation. PostgreSQL is
local through Homebrew, not Docker; the existing system cluster is left untouched.
See [database design/setup](database.md) for the ERD and exact constraints.

## Planned service boundaries

Future schemas will validate API input/output. Future services will enforce actor
permissions, booking transitions, ownership, server-side pricing and capacity inside
transactions. A future security package will handle authentication/authorisation.
These packages are not created empty for appearance. A user can optionally host
through a shared-key HostProfile, without a second account model.

The [booking state machine](booking-state-machine.md) proposes locking the listing
row before reservation-changing operations. This is a design for later code, not a
capacity guarantee already implemented. See [ADR 0001](adr/0001-boarding-relational-model.md)
for persistence trade-offs.

## Future external integrations (not implemented)

Stripe TEST mode, authenticated/idempotent webhooks, maps/geocoding, image/object
storage and transactional email remain planned. No SDKs, payment logic, network
callbacks or fake provider implementations were added. External operations must not
run while holding a reservation transaction's database locks.

Only explicit local CORS origins are allowed. Credentials remain server-side;
VITE_ variables are public and must never contain secrets. The local migration-owner
roles are appropriate for this milestone, not a substitute for deployment hardening.

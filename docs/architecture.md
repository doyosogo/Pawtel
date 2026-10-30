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
No marketplace or polished authentication UI has been built. Future features can live
under src/features when real requirements exist.

FastAPI app/main.py owns lifespan/CORS and preserves /health and exposes versioned /api/v1/auth and /api/v1/pets routes beyond framework
documentation. app/core reads root .env and environment overrides. app/db owns named
metadata, a lazy engine and per-operation sessions. Startup and health do not create
an engine or require PostgreSQL. Sessions clean up resources but future services
must explicitly own transaction boundaries.

app/models contains typed account, pet, listing and booking persistence models, with
common UUID/timestamp mixins and native enum declarations. An explicit registry in
app/models/__init__.py imports every model; Alembic imports it for complete metadata.
TYPE_CHECKING imports and SQLAlchemy forward relationships avoid runtime model
import cycles. These are database models, not Pydantic API schemas. Pet Profiles
are exposed only through owner-scoped services. Listings now have private verified-host
management APIs; public marketplace browsing
and booking workflows remain deferred. Authentication uses explicit
Pydantic input/output schemas, not general ORM serialization.

Alembic owns schema creation and versioning. The initial migration is independent
of mutable model definitions and owns native enum creation/removal. There is no
startup create_all. Real PostgreSQL integration tests use these migrations, a
separate protected test database and rollback/savepoint isolation. PostgreSQL is
local through Homebrew, not Docker; the existing system cluster is left untouched.
See [database design/setup](database.md) for the ERD and exact constraints.

## Planned service boundaries

app/schemas now validates auth input/output; app/services/auth owns transactional
registration/session/verification operations. app/security owns Argon2id, random
credentials, request/CSRF checks and identity/active/verified dependencies. Safe
application errors are defined in app/api/errors. Future business services must
add ownership, booking transitions, pricing and capacity transaction rules. A user can optionally host
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

## Authentication boundary

Opaque sessions use PostgreSQL rather than JWT/Redis. HttpOnly cookies carry raw
random credentials; database lookup uses SHA-256 digests. Argon2id stores passwords.
Credentialed CORS is exact-origin, and auth POSTs combine JSON/custom-header/Origin
checks with a session synchronizer nonce when authenticated. Registration and email
verification use explicit atomic transactions. Email delivery remains deferred.
See [ADR 0002](adr/0002-opaque-session-authentication.md) and
[authentication/security](authentication.md) for actual semantics and limitations.

## Private Pet resource boundary

Milestone 4 reuses the existing Pet schema/index. app/schemas/pets validates and
whitelists profile data; app/services/pets owns explicit transactions and owner-scoped
SQL reads/updates; app/api/v1/pets supplies identity from the active-user dependency.
The router reuses synchronizer CSRF for writes. Missing and foreign resources share
404, and DELETE archives instead of deleting. /api/v1 responses are no-store;
credentialed CORS additionally allows PATCH/DELETE for the same exact origins.
No explicit row locks/versioning or generic repository framework was introduced.
See [Pet ownership design](pet-profiles.md) and [ADR 0003](adr/0003-private-pet-ownership.md).

## Host management boundary (Milestone 5)

The existing verified-user dependency gates all private Host endpoints. Focused Host
and Listing services derive the shared HostProfile key from authenticated identity,
use owner-scoped SQL and own atomic Listing/species transactions. Explicit response
schemas avoid relationship/security serialization. No migration or new infrastructure
was necessary. See [Host/Listing contract](host-listings.md) and ADR 0004 for lifecycle,
archive, validation and current last-writer-wins limitations.

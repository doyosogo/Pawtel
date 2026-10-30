# PAWTEL

PAWTEL is a planned Airbnb-style pet boarding marketplace across Australia for owners
of dogs/cats and accommodation hosts. One account will support optional Host mode.
This flagship junior software engineering portfolio project emphasises relational
design, backend correctness, secure workflows and maintainable frontend engineering.

**Status: Milestone 5 — private Host and Listing management.** Implemented:
registration/session authentication, private Pet Profiles, optional Host mode and
verified-host Listing configuration. Listing management is private: even PUBLISHED
records have no public browsing/search endpoint. No Host/Pet frontend, external email
delivery, booking/availability/quote/payment workflow or polished UI exists yet.

## Stack and layout

- React 19, TypeScript 6, Vite 8, Tailwind CSS 4, React Router 8, TanStack Query 5, Zustand 5
- Python 3.14, FastAPI, Pydantic v2 / Settings, SQLAlchemy 2, Alembic, Psycopg 3, Uvicorn
- PostgreSQL 18 stable; Homebrew local setup, no Docker
- Vitest / React Testing Library, ESLint / Prettier, Pytest / Ruff

```text
frontend/src/app/       # Routing/providers
frontend/src/pages/     # Temporary screen and smoke test
backend/app/api/        # Health, versioned auth/pet/host routes and safe errors
backend/app/core/       # Environment settings
backend/app/db/         # Base metadata, lazy engine/session infrastructure
backend/app/models/     # Domain and authentication persistence
backend/app/schemas/    # Explicit auth, pet and host input/output contracts
backend/app/services/   # Focused transactional auth/pet/host operations
backend/app/security/   # Credentials, CSRF and permission dependencies
backend/alembic/        # Migration environment and versioned schema
backend/tests/          # Health/safety unit tests and PostgreSQL integration tests
backend/.venv/          # Ignored local Python environment
docs/                  # Scope, architecture, database ERD, state design, ADR
.env.example            # Safe placeholders; local .env is ignored
```

See [product scope](docs/product-scope.md), [architecture](docs/architecture.md),
[database design and macOS setup](docs/database.md), [booking state machine](docs/booking-state-machine.md),
[ADR 0001](docs/adr/0001-boarding-relational-model.md) and [engineering principles](docs/engineering-principles.md).
See [authentication/security](docs/authentication.md), [ADR 0002](docs/adr/0002-opaque-session-authentication.md)
and [authentication interview notes](docs/authentication-interview.md) for this milestone.
See [Pet Profiles and ownership](docs/pet-profiles.md) and
[ADR 0003](docs/adr/0003-private-pet-ownership.md) for Milestone 4.

## Prerequisites

- macOS with Homebrew for the documented local database setup.
- Node 24 LTS recommended (verified 24.13.1), or supported Node 22.22+; npm 11.8.0 verified.
- Python 3.14 with pip/venv (verified 3.14.8). The requirement excludes unverified Python 3.15.
- PostgreSQL 18 stable (verified Homebrew 18.6); do not use PostgreSQL 19 RC.

`frontend/package-lock.json` and `backend/requirements-dev.lock` are intended for
version control. The latter is a pinned pip snapshot of runtime + development
packages, generated on macOS ARM64/Python 3.14.8 with
`python -m pip freeze --exclude pawtel-backend`. It excludes the editable project
and local paths, has no hashes and is not a universal cross-platform resolver lock.
Update dependencies deliberately in a clean environment and rerun checks before
regenerating it. Milestone 3 adds argon2-cffi and email-validator plus their required
transitive packages; earlier pins are unchanged.
TypeScript 6 satisfies the current typescript-eslint support range; jsdom 29 supports
the verified Node runtime. Zustand is installed without an artificial store.

## PostgreSQL setup on macOS

Inspect installed servers first. This Mac already has PostgreSQL 18.4 under
`/Library/PostgreSQL/18` on port 5432, which remains untouched. PAWTEL uses a separate
Homebrew PostgreSQL 18.6 cluster on **127.0.0.1:5433**, with a separate socket directory.
Do not overwrite unrelated clusters or assume port 5432 is free.

```zsh
brew install postgresql@18
```

Before starting a fresh Homebrew cluster, configure its port, listener, socket and
authentication using the exact [local setup instructions](docs/database.md#reproduce-the-isolated-setup-on-macos).
Those instructions also create separate non-superuser roles/databases `pawtel_dev`
and `pawtel_test`, prompt securely for different passwords, revoke PUBLIC database
access and configure UTC role timezones. They are first-time creation instructions;
do not rerun them blindly over existing roles/data.

Then manage only the Homebrew service:

```zsh
brew services start postgresql@18
brew services list
"$(brew --prefix postgresql@18)/bin/pg_isready" -h 127.0.0.1 -p 5433
brew services stop postgresql@18
```

Start it again before migration/integration tests. `brew services restart postgresql@18`
restarts it. This does not manage the separate /Library installation.

## Environment

On a fresh checkout, from the root:

```zsh
cp .env.example .env
chmod 600 .env
```

**Preserve an existing .env**; this workspace already has generated local credentials.
Replace example passwords with the actual respective role passwords. URI-encode
special characters. DATABASE_URL points to pawtel_dev; TEST_DATABASE_URL points to
pawtel_test. Both target 127.0.0.1:5433 on this Mac. Never put these values in Git or
frontend VITE_ variables, which are public.

Pydantic Settings reads root .env regardless of the backend working directory.
Environment variables override file values. BACKEND_CORS_ORIGINS is a JSON array,
configured as `["http://localhost:5173"]` for local development. The code defaults
to no allowed origins, APP_ENV=production and Secure cookies. The local .env example
explicitly chooses APP_ENV=development and SESSION_COOKIE_SECURE=false for HTTP.
Production rejects insecure cookies and non-HTTPS origins. Startup/health work
without database URLs; authentication and migrations need their configured database.

## Backend setup, migrate and run

From the root:

```zsh
cd backend
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
python -m alembic upgrade head
python -m alembic current
python -m alembic history
python -m alembic check
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Install Python 3.14 first if missing. This workspace has an ignored project-local
runtime under backend/.python and a ready .venv. `.python-version` contains `3.14` as
a version-manager hint; it does not change system Python. Use `deactivate` to leave
the virtual environment.

http://localhost:8000/health returns `{"status":"ok"}`; /docs shows the API docs.
Health is liveness, not database readiness. Application startup never creates tables
or opens a connection. Alembic creates the schema, not startup create_all.

## Backend verification and integration tests

From backend with .venv active and both databases configured:

```zsh
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -m pytest -m integration
python -m pip check
python -c 'from app.main import app; print(app.title)'
python -m compileall -q app
python -m alembic check
```

Default pytest includes real PostgreSQL tests. They guard the exact local test
name/role, reject development targets and unsafe URL options, verify PostgreSQL 18,
apply real migrations and roll model changes back after every test. The guarded
migration test downgrades/upgrades **only the empty test database** and checks enum
cleanup. Do not store valuable data in pawtel_test or run parallel test workers
against it. See [test isolation/safety](docs/database.md#integration-testing-and-safety).

For database-independent health and safety tests only:

```zsh
python -m pytest -m 'not integration'
```

Format Python with `python -m ruff format .`. Python has no separate application
build step; import/compile checks verify it. No frontend calls to domain APIs exist.

## Frontend setup and verification

From the root, in another terminal:

```zsh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173 for the temporary screen. It needs no frontend environment
variables and does not fetch backend data yet.

```zsh
npm run lint
npm test -- --run
npm run build
npm run format:check
```

`npm run preview` serves the build; `npm run format` formats source.

## Exercise authentication locally

After applying migrations and starting Uvicorn, follow the
[local HTTPX example](docs/authentication.md#local-exercise-no-credentials-printed).
It prompts for a password without printing it, exercises registration/login/me/logout
and keeps the cookie only in memory. All auth POSTs require JSON and
`X-PAWTEL-Request: 1`. Authenticated POSTs also require the session nonce obtained
through GET `/api/v1/auth/csrf`, supplied in `X-CSRF-Token`. Browser fetch calls must
use `credentials: 'include'` and the configured exact frontend Origin.

Registration returns 201 with a safe User and `verification_delivery: "not_configured"`.
Login returns 200, sets the HttpOnly cookie and permits an unverified active user to
hold a limited session. GET `/api/v1/auth/me` returns only safe self fields. Logout
revokes only the current session and clears the cookie; repeated unauthenticated
logout returns 204. POST `/api/v1/auth/verify-email` consumes a valid capability
transactionally, but no email provider exposes/delivers that raw token yet. The
integration tests exercise it through internal service helpers. Do not print or
return secret tokens as a development shortcut.

## Pet Profiles API

All endpoints require a valid session and active account. Verified email is not
required for private profile preparation; later marketplace actions will require it.
POST `/api/v1/pets` creates an owned Pet; GET lists active own pets (optionally
`?include_archived=true`); GET/PATCH/DELETE `/api/v1/pets/{pet_id}` operate only on
that owner's Pet. DELETE archives rather than physically deleting. Foreign/missing
valid UUIDs share 404 `pet_not_found`; malformed UUIDs return safe 422 validation errors.

Writes require the existing JSON, `X-PAWTEL-Request: 1`, valid Origin when supplied,
and session `X-CSRF-Token` protections. DELETE sends `{}`. Never send owner_id or
other immutable fields in request JSON. No schema/index change or migration was
needed; Alembic remains at `868589ec460a`. See the [Pet API contract](docs/pet-profiles.md)
for validation, sparse PATCH, archived metadata edits and last-writer-wins limitations.
No Pet management frontend exists yet.

## Deliberate limitations

No email delivery, public resend endpoint, password reset, OAuth, MFA, polished auth
UI or booking/payment workflows are implemented. Before public deployment,
add rate limiting/credential-stuffing controls, email recovery/delivery, deployment
hardening and session cleanup/retention. Current security tests reduce risk but do
not establish timing immunity or complete production security.

Domain constraints still do not enforce per-night capacity, booking state transitions,
pet/booking owner matching or pricing formulas. Those belong to later transactional
services and concurrency tests. Search, messaging, reviews, maps, notifications,
images and admin functionality also remain deferred. There is no measured index
performance claim or production runtime/migration-role separation yet.

## Host and Listing management (Milestone 5)

See [Host/Listing API contract](docs/host-listings.md) and
[ADR 0004](docs/adr/0004-verified-private-host-management.md).
All `/api/v1/host` reads and writes require an active, authenticated, email-verified
User. POST `/profile` enables Host mode on that same account; GET/PATCH `/profile`
read/edit its optional bio. POST/GET `/listings` and GET/PATCH/DELETE
`/listings/{listing_id}` manage only that Host's Listings. Writes use the same JSON,
request-marker, Origin and session-CSRF protections as Pet writes; DELETE sends `{}`.
There is no real email provider yet; tests verify accounts using internal token
issuance, without exposing tokens in production API responses.

Creation always produces DRAFT. PATCH can select DRAFT/PUBLISHED; publication needs
at least one accepted species. DELETE archives permanently through this API while
preserving the row. No public visibility is implemented. Prices are strict integer
cents; capacity is configuration, not date availability. No migration/index/dependency
change was needed; revision remains `868589ec460a`.

# PAWTEL

PAWTEL is a planned Airbnb-style pet boarding marketplace across Australia for owners
of dogs/cats and accommodation hosts. One account will support optional Host mode.
This flagship junior software engineering portfolio project emphasises relational
design, backend correctness, secure workflows and maintainable frontend engineering.

**Status: Milestone 2 — PostgreSQL and relational persistence.** Implemented: a
temporary React screen, FastAPI settings/CORS/health, seven relational domain tables,
the first Alembic migration and real PostgreSQL integration tests. Authentication,
booking workflows, capacity handling, price calculation and payments are **planned,
not implemented**. No marketplace endpoints or final frontend UI exist yet.

## Stack and layout

- React 19, TypeScript 6, Vite 8, Tailwind CSS 4, React Router 8, TanStack Query 5, Zustand 5
- Python 3.14, FastAPI, Pydantic v2 / Settings, SQLAlchemy 2, Alembic, Psycopg 3, Uvicorn
- PostgreSQL 18 stable; Homebrew local setup, no Docker
- Vitest / React Testing Library, ESLint / Prettier, Pytest / Ruff

```text
frontend/src/app/       # Routing/providers
frontend/src/pages/     # Temporary screen and smoke test
backend/app/api/        # Health endpoint only
backend/app/core/       # Environment settings
backend/app/db/         # Base metadata, lazy engine/session infrastructure
backend/app/models/     # Typed relational models, separate from future API schemas
backend/alembic/        # Migration environment and versioned schema
backend/tests/          # Health/safety unit tests and PostgreSQL integration tests
backend/.venv/          # Ignored local Python environment
docs/                  # Scope, architecture, database ERD, state design, ADR
.env.example            # Safe placeholders; local .env is ignored
```

See [product scope](docs/product-scope.md), [architecture](docs/architecture.md),
[database design and macOS setup](docs/database.md), [booking state machine](docs/booking-state-machine.md),
[ADR 0001](docs/adr/0001-boarding-relational-model.md) and [engineering principles](docs/engineering-principles.md).
Future API schemas, services and security packages will be introduced when needed.

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
regenerating it. No Python dependency changes were needed for this milestone.
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
defaulting to `["http://localhost:5173"]`. Startup and health work without either
database URL; migration/database operations require their appropriate URL.

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

## Deliberate limitations

Models and constraints are not complete product features. The database does not yet
enforce pet/booking ownership matching, legal state transitions, per-night capacity,
price formulas, permissions or payment verification. Those transactional services,
meaningful concurrency tests and external integrations belong to later milestones.
Search, messaging, reviews, maps, notifications, image storage and admin functionality
are also deferred. There is no claim of measured index performance or production
runtime/migration-role separation yet.

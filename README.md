# PAWTEL

PAWTEL is a planned Airbnb-style marketplace for pet boarding across Australia, serving owners of dogs and cats and hosts offering accommodation. One account will support both owner use and optional Host mode.

This flagship software engineering portfolio project aims to demonstrate substantial backend development, relational design, secure business workflows and polished frontend engineering for junior developer and software engineer roles.

**Status: foundation milestone only.** The temporary frontend, API health endpoint, configuration, database infrastructure and development tooling are implemented. PostgreSQL installation, domain models and marketplace functionality belong to later milestones.

## Stack

- React 19, TypeScript 6, Vite 8, Tailwind CSS 4, React Router 8, TanStack Query 5, Zustand 5
- Python 3.14, FastAPI, Pydantic v2, Pydantic Settings, SQLAlchemy 2, Alembic, Psycopg 3, Uvicorn
- Planned database: PostgreSQL
- Quality: ESLint, Prettier, Vitest, React Testing Library, Pytest, Ruff

`frontend/package-lock.json` and `backend/requirements-dev.lock` record verified dependency versions and are intended to be committed. The backend file is a pinned pip requirements snapshot of runtime and development dependencies, generated from the clean Python 3.14 macOS environment with `python -m pip freeze --exclude pawtel-backend`. It excludes the editable project and local paths. It is not a cross-platform resolver lock or a hash-verified supply-chain lock; other platforms must be verified separately. When changing dependencies, update `pyproject.toml`, install into a clean environment, regenerate this snapshot and rerun checks. TypeScript 6 is selected because current typescript-eslint does not support TypeScript 7. jsdom 29 supports the installed Node runtime; jsdom 30 requires a newer Node patch. Zustand is installed for future client state without an artificial store.

## Repository structure

```text
PAWTEL/
  frontend/
    src/app/          # Providers and routing
    src/pages/        # Temporary screen and component test
    src/test/         # Test setup
  backend/
    app/api/          # Health route
    app/core/         # Environment settings
    app/db/           # Empty metadata, lazy engine and sessions
    alembic/          # Migration infrastructure; no domain revisions
    tests/
    .venv/            # Ignored local virtual environment
  docs/
  .env.example
  .gitignore
  .editorconfig
  README.md
```

Future frontend features can live under `src/features`. Backend models, schemas, services and security packages will be introduced when needed. See [product scope](docs/product-scope.md), [architecture](docs/architecture.md) and [engineering principles](docs/engineering-principles.md).

## Prerequisites

- Node.js 24 LTS recommended (verified with 24.13.1); Node 22.22+ is also supported by the selected tools.
- npm (verified with 11.8.0).
- Python 3.14 with pip and venv (verified with 3.14.8).

PostgreSQL and Docker are not required for this milestone. No global Node or Python packages need to be installed for the application.

## Environment

From the root, optionally copy the safe example:

```zsh
cp .env.example .env
```

The backend reads this root file regardless of working directory. Environment variables take precedence. `BACKEND_CORS_ORIGINS` is a JSON array, defaulting to `["http://localhost:5173"]`. `DATABASE_URL` has no default credentials and is optional until database operations are introduced. Its example is commented out: replace placeholders only when configuring PostgreSQL in the next milestone.

Never commit `.env` or real credentials. Frontend `VITE_` variables are public and must not contain secrets. The placeholder requires no frontend environment variables.

## Frontend setup and run

From the repository root:

```zsh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. This screen is temporary and does not yet fetch API data.

## Backend setup and run on macOS

In a separate zsh terminal, from the repository root:

```zsh
cd backend
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If Python 3.14 is not installed, install it from python.org first. This workspace has an ignored project-local Python runtime under `backend/.python`; its existing `.venv` is ready to activate. The standard setup above is the reproducible path for a new checkout. Run `deactivate` to leave the virtual environment. `backend/.python-version` contains `3.14` as a version-manager hint aligned with `requires-python`; it does not install Python or change the system interpreter.

Open http://localhost:8000/health for `{"status":"ok"}` and http://localhost:8000/docs for API documentation. Startup and health do not create an engine, open a database connection or create tables. Health reports application liveness; it does not report database readiness.

## Tests, lint and build

From `frontend/`:

```zsh
npm run lint
npm test -- --run
npm run build
npm run format:check
```

`npm run preview` serves the production build locally. `npm run format` formats frontend source.

From `backend/`, using the project virtual environment:

```zsh
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest
.venv/bin/python -m pip check
.venv/bin/python -c 'from app.main import app; print(app.title)'
.venv/bin/python -m compileall -q app
.venv/bin/python -m alembic history
```

There is no separate backend application build step; import and bytecode compilation check the Python application. Tests explicitly exercise application lifespan and ensure health cannot connect to PostgreSQL. They also verify allowed and disallowed CORS origins. Format Python with `.venv/bin/python -m ruff format .`.

## Deliberate limitations

No authentication, pet profiles, listings, bookings, payments, messaging, search, reviews, maps or dashboards are implemented. No database entities or migration revisions exist. Alembic is prepared against empty metadata; database migration execution requires a configured PostgreSQL connection later. Session cleanup exists, while future services must define transaction boundaries explicitly. Stripe, geocoding, object storage and transactional email are planned integrations only.

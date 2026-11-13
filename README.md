# PAWTEL

[![PAWTEL CI](https://github.com/doyosogo/Pawtel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/doyosogo/Pawtel/actions/workflows/ci.yml)

An Australian **pet-boarding marketplace** for dog/cat Owners and Hosts: discover a
stay, request a Booking, accept it as Host and complete Stripe **test** checkout.
A production-shaped full-stack portfolio MVP built with **React, TypeScript,
FastAPI and PostgreSQL**. Boarding is the current service scope; this is not a
production-ready service or a real accommodation offer.

**Verified:** 520 backend tests · 157 frontend tests · 3 full-stack E2E tests · 3 static showcase E2E tests.
GitHub-hosted [run 43339550717](https://github.com/doyosogo/Pawtel/actions/runs/43339550717)
is fully green for `main` commit `f1f87d8` (backend, frontend and E2E).

## Frontend showcase

<!-- FRONTEND_SHOWCASE_URL: replace the next paragraph only after manual verification. -->

**Vercel showcase: not deployed — URL pending manual deployment.**

The static **Frontend Showcase — synthetic data** reuses PAWTEL's React UI with
local simulated actions. Explore as Owner or Host without passwords, backend or
provider setup. No real accounts, bookings or payments are created.
[Run or deploy the showcase](docs/frontend-showcase.md).

## Full-stack implementation and hosted demo

This repository contains the real React → FastAPI → PostgreSQL implementation,
including session/CSRF security, Booking concurrency, Stripe and Cloudinary.
The showcase complements this implementation; it does not replace it.

<!-- LIVE_DEMO_STATUS: replace only the next paragraph after a real public URL is verified. -->

**Full-stack Render demo: not deployed — provisioning and verification remain manual.**

See the [deployment guide](docs/deployment.md) and [final handoff](docs/deployment-checklist.md).
The full-stack synthetic demo uses privately shared access and server-disabled
registration. No reusable password belongs in this repository.

## Engineering highlights

- Prevent foreign-resource access with session-derived identity and owner-scoped
  Pet, Listing and Booking queries; protect cookie-authenticated writes with CSRF.
- Serialize Host acceptance with PostgreSQL Listing-first row locks, then recheck
  overlapping Pet capacity before reserving the final space.
- Persist server-owned AUD price snapshots instead of trusting client totals.
- Confirm payments through signed, deduplicated webhooks; reconcile uncertain
  Checkout outcomes and late payment after cancellation without resurrecting bookings.
- Track Cloudinary upload/delete partial failures with durable media states and
  cleanup instead of pretending the provider and PostgreSQL share a transaction.
- Verify real React → FastAPI → PostgreSQL journeys in isolated CI; diagnose
  failures with safe JSON logs, request IDs and separate health/readiness checks.

[Architecture and Booking data flow](docs/architecture.md) ·
[Portfolio case study](docs/portfolio-case-study.md) · [Documentation index](docs/README.md)

## Stack

React 19, TypeScript 6, Vite 8, Tailwind 4, React Router and TanStack Query;
Python 3.14, FastAPI, SQLAlchemy, Psycopg and Alembic; PostgreSQL 18;
Stripe Checkout Elements and Cloudinary; Pytest, Vitest/Testing Library,
headless Playwright and GitHub Actions. Server state stays in TanStack Query;
Zustand is installed but no artificial duplicated API store was added.

## Run locally from a clean clone

Prerequisites: Python **3.14**, Node **24** (or supported 22.22+), and PostgreSQL **18**.
Use the [database setup](docs/database.md#reproduce-the-isolated-setup-on-macos) to
create separate non-superuser `pawtel_dev` and `pawtel_test` roles/databases.
The documented macOS cluster uses loopback port **5433**; adapt connection URLs to
your own isolated PostgreSQL 18 setup. Do not overwrite unrelated clusters/data.
Linux CI uses disposable PostgreSQL containers; Docker is not required locally.

From repository root, on a fresh clone only:

```bash
cp .env.example .env
chmod 600 .env
cd backend
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
```

Edit the ignored root `.env`: replace database password placeholders with your own
URI-encoded credentials, keep `APP_ENV=development`, `SESSION_COOKIE_SECURE=false`,
`SERVE_FRONTEND=false` and `PORTFOLIO_DEMO=false` for local Vite development.
`DATABASE_URL` targets `pawtel_dev`; `TEST_DATABASE_URL` targets `pawtel_test`.
Do not overwrite an existing `.env`, commit it or expose either URL through VITE_.

Backend terminal, from repository root:

```bash
cd backend
source .venv/bin/activate
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Frontend terminal, from repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Backend diagnostics are `http://localhost:8000/health`
and `/ready`; development API docs are `/docs`. Production does not use reload.
Only public `VITE_` settings reach the frontend; ordinary API calls use the local
Vite proxy and one relative `/api/v1` base.

## Try the full workflow locally

PAWTEL uses **email-based login**, not an `admin/admin` account. Choose your own
15–128 character passphrase in the ignored root `.env`:

```dotenv
PAWTEL_DEMO_PASSWORD=<your-local-demo-password>
```

That is a placeholder, not a usable password. After migrations, from repository root:

```bash
cd backend
source .venv/bin/activate
python -m app.scripts.seed_workflow
```

This guarded local command creates/updates:

| Role  | Login email                         |
| ----- | ----------------------------------- |
| Owner | `workflow.owner@pawtel.example.com` |
| Host  | `workflow.host@pawtel.example.com`  |

Use the local passphrase you chose for either synthetic account. Passwords are
hashed normally with **Argon2id**; no authentication bypass exists and no password
is stored in Git. These identities are marked verified only because the operator
explicitly creates fictional test users. Normal registration does not bypass email
verification. Email delivery is not implemented; no verification email is promised.

The Owner has a DOG and CAT; the Host owns **Demo workflow garden stay**. No Bookings
are seeded. The command is idempotent and preserves existing edits/history; password
rotation revokes synthetic sessions. It is not a destructive reset. Prefer fresh
future dates and the workflow Host's Listing rather than passwordless browse-only seeds.

1. Log in as Owner and inspect **My Pets**.
2. Search **Norwood**, open **Demo workflow garden stay**, select future check-in/
   checkout and an accepted Pet, then **Request booking**.
3. Inspect the server price snapshot and **Waiting for the Host to respond**.
4. Log out, then log in as Host.
5. Open **Host workspace → Booking inbox**, open the request and accept it.
6. Log out and return as Owner; open **My Bookings** and observe **Payment required**
   (`AWAITING_PAYMENT`), authoritative total and deadline.
7. Optionally continue through **Pay securely** only after [Stripe sandbox setup](docs/payments.md).
   A browser return alone does not confirm payment: the verified webhook must arrive.

**Which seed?** `seed_workflow` is development-only, guarded to local `pawtel_dev`.
The optional `seed_demo` command supplies fictional browse-only Listings with
passwordless Hosts. `seed_portfolio` is a separate operator-only command for a
managed, dedicated synthetic deployment; do not use it for local setup or real users.
See [deployed demo controls](docs/deployment.md#5-prepare-safe-synthetic-access).
All demo identities, Pets and accommodations are fictional. Use synthetic inputs only.

## Tests and CI

Backend, from repository root (PostgreSQL 18 and both database URLs required):

```bash
cd backend
source .venv/bin/activate
python -m pytest
```

Frontend, from repository root:

```bash
cd frontend
npm test -- --run
```

E2E needs an additional guarded **pawtel_e2e** database AND role, plus a private
`E2E_DATABASE_URL`. Follow the [isolated setup](docs/operations.md#isolated-headless-e2e),
then from `frontend`:

```bash
PLAYWRIGHT_BROWSERS_PATH=../.cache/pw-browsers npm run e2e:install
npm run test:e2e
```

The runner uses real React → FastAPI → PostgreSQL, unique synthetic fixtures and
scoped cleanup. It refuses developer/production databases. Only bundled headless
Chromium is used; screenshot/trace/video recording is disabled. Normal CI does not
contact Stripe, Cloudinary or an email service.

GitHub Actions checks clean locked installs, PostgreSQL, migrations, Ruff and
formatting, complete backend tests/dependency consistency, ESLint, Vitest,
TypeScript/Vite build, Prettier and isolated E2E. PR CI receives no deployment/provider
secrets and never deploys. [Runbook and complete commands](docs/operations.md).
The [first CI failure and verified recovery](docs/portfolio-case-study.md#cie2e-and-deployment-hardening)
show why explicit test configuration matters.

## Read further

[Authentication](docs/authentication.md) · [Pets](docs/pet-profiles.md) ·
[Bookings](docs/bookings.md) · [Payments](docs/payments.md) ·
[Host/Listings/media](docs/host-listings.md) · [Discovery](docs/listing-discovery.md) ·
[Operations](docs/operations.md) · [Deployment](docs/deployment.md) · [ADRs](docs/adr/README.md)

[Résumé material](docs/resume-bullets.md) · [Interview guide](docs/interview-guide.md) ·
[Manual screenshot plan](docs/images/README.md)

## Current limits

Not production-ready: sandbox-only payments; no real email delivery/recovery,
reviews, messaging, notifications, admin, payouts or maps. Hosting is prepared but
not provisioned or publicly verified. Demo request budgets are single-process,
not distributed abuse protection. Load/security assessment, restore drills,
operational scheduling, final CSP/provider verification and customer/privacy/support
processes remain launch work. Known development-tooling advisories are documented
in [operations](docs/operations.md#dependency-review-observed-locally); no Python
vulnerability-free claim is made.

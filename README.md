# PAWTEL

PAWTEL is a planned Airbnb-style pet boarding marketplace across Australia for owners
of dogs/cats and accommodation hosts. One account will support optional Host mode.
This flagship junior software engineering portfolio project emphasises relational
design, backend correctness, secure workflows and maintainable frontend engineering.

**Status: Milestone 12 — Host onboarding, Listing management and Cloudinary media.** Implemented:
registration/session authentication, private Pet Profiles, optional Host mode and
verified-host Listing configuration, plus published-only public discovery/detail and
date-aware capacity snapshots. Owners can request stays with server-priced quotes;
Hosts accept/decline, and Owners cancel before payment. Acceptance reserves capacity
transactionally. Owners can start Stripe sandbox Checkout; verified paid webhooks
confirm bookings and expiry releases holds. No live charges, payouts, external email
delivery exists. The Owner sandbox Checkout Elements UI is documented below.

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
build step; import/compile checks verify it.

## Frontend setup and verification

From the root, in another terminal:

```zsh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173 for the marketplace. Start the backend on port 8000
in another terminal first. Vite proxies `/api` to `http://127.0.0.1:8000`, preserving
the browser origin for cookie sessions and CSRF checks. No frontend environment
variables or credentials are needed. Use localhost:5173 (the configured allowed
origin), rather than a LAN IP. Port 5173 is strict, so Vite will report a conflict
instead of silently choosing another origin.

Routes include the homepage, `/stays`, `/stays/:listingId`, `/register`, `/login`,
and `/account`; `/hosting` explains the current hosting status without management
tools. Search uses the real discovery filters and server pagination. Availability
checks do not reserve a stay. Registration does not send email in this demo, and
verified email remains required by the backend for hosting and bookings.

React Router handles routes; TanStack Query handles server/session state. API
requests include cookies. Writes fetch the current session CSRF nonce and include
`X-PAWTEL-Request: 1`; passwords and session credentials are never persisted in
browser storage. Local SVG illustrations are visibly labelled demo imagery.

Optional fictional marketplace data, from the backend directory with its virtual
environment active:

```zsh
python -m app.scripts.seed_demo
```

This create-only command requires APP_ENV=development and the local `pawtel_dev`
database/role, rejects URL options and superuser execution, uses deterministic IDs
and a transaction advisory lock, and preserves existing rows and edits. It creates
12 fictional published Listings and passwordless hosts under reserved `.test`
email addresses. Reruns create zero Listings when all demo rows already exist.
There is no reset operation and seeded hosts cannot log in. Never use it to load
production data.

```zsh
npm run lint
npm test -- --run
npm run build
npm run format:check
```

`npm run build` includes `tsc -b` type checking. `npm run preview` serves the build;
`npm run format` formats source. The `/api` proxy is a development-server feature;
production hosting must route `/api` to the backend and serve the SPA fallback.
Run npm commands from `frontend`, which contains package.json.

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
UI or live payment/payout workflows are implemented. Before public deployment,
add rate limiting/credential-stuffing controls, email recovery/delivery, deployment
hardening and session cleanup/retention. Current security tests reduce risk but do
not establish timing immunity or complete production security.

Domain constraints alone do not enforce per-night capacity, booking transitions,
pet ownership or pricing formulas. Milestone 7 services enforce these for pre-payment
requests/actions; sandbox payment/expiry transitions now follow the same protocol. Ranked/geospatial search, messaging, reviews, maps, notifications,
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
preserving the row. Public visibility now exists only for PUBLISHED records through the separate Milestone 6 API. Prices are strict integer
cents; capacity is configuration, not date availability. No migration/index/dependency
change was needed; revision remains `868589ec460a`.

## Public Listing discovery (Milestone 6)

GET `/api/v1/listings` supports location, all-requested species, base-price and capacity
filters with bounded limit/offset pagination. GET `/api/v1/listings/{id}` exposes only
published details and safe Host display information. GET
`/api/v1/listings/{id}/availability?check_in=2027-11-10&check_out=2027-11-12&pet_count=1`
returns advisory remaining capacity. Dates in collection search require pet_count too.
No authentication/CSRF is required for these read-only endpoints. Draft/archived/missing
records share public 404. Availability is NOT a reservation; acceptance must recheck
transactionally later. Milestone 7 adds the separate pre-payment Booking API; no frontend was added. See
[discovery contract](docs/listing-discovery.md) and
[ADR 0005](docs/adr/0005-advisory-public-availability.md).

## Booking requests before payment (Milestone 7)

Verified active Owners can POST `/api/v1/bookings` with listing_id, distinct owned
pet_ids and check_in/check_out. The server validates published visibility, pets,
species, UTC dates and advisory capacity, calculates integer-cent prices plus a
10% HALF-UP fee, and stores immutable request snapshots. REQUESTED reserves nothing.
Owner GET collection/detail and POST `/{id}/cancel` are private. Verified Hosts GET
`/api/v1/host/bookings` and detail, then POST `/{id}/accept` or `/decline`.

Acceptance locks Listing then Booking and rechecks per-night capacity before
AWAITING_PAYMENT; simultaneous last-space acceptances cannot both succeed through
this service. Cancellation releases holds under that same protocol. Configure
BOOKING_PAYMENT_WINDOW_SECONDS (default 1800); overdue holds still reserve until an
explicit future expiry transition. No Stripe/payment-success/expiry scheduler exists.
All writes use existing CSRF/request protections. Creation is not idempotent: do not
blindly retry unknown outcomes. See [Booking contracts](docs/bookings.md) and
[ADR 0006](docs/adr/0006-listing-locks-and-booking-quotes.md). No migration was needed.

## Stripe sandbox payments (Milestone 8)

Apply migration b690ce0b281d and configure safe test-only Stripe settings in ignored
.env; never commit keys/signing/client secrets. Verified Owners POST
`/api/v1/bookings/{id}/checkout-session` with `{}` and normal CSRF protections.
Checkout uses accepted price snapshots, elements/payment/AUD/card-only and fixed
attempt idempotency keys. Only signed raw-byte Stripe webhooks confirm payment;
a frontend redirect cannot. Paid cancellation races require reconciliation, not
resurrection or automatic refunds. No Host payouts/Connect or polished checkout exists.

See [payment contracts/recovery/CLI workflow](docs/payments.md),
[ADR 0007](docs/adr/0007-checkout-and-webhook-authority.md) and
[payment interview notes](docs/payments-interview.md). Explicit maintenance can be
run from backend with `python -m app.payments.maintenance --limit 100`; it expires
unstarted overdue holds or reconciles provider sessions without bypassing webhook
confirmation. No automatic scheduler is installed. Normal tests use offline provider
fakes and require PostgreSQL, not Stripe internet. Real sandbox smoke verification
is a separate check and requires safely provisioned test credentials.

## Booking website and local workflow demo (Milestone 10)

The public marketplace keeps its existing search, Listing details and advisory
availability checks. The account menu now links to My Pets, My Bookings and the
Host workspace. Private routes redirect to login with a return path; the API still
enforces ownership, active accounts, verified email, CSRF and Booking transitions.

- `/account/pets`: active/archived Pet collection, create/edit and confirmed archive.
  Only name, DOG/CAT species, optional breed and optional birth date are editable.
- `/account/bookings` and `/:bookingId`: Owner history, saved server prices,
  status/deadline, manual refresh and cancellation of REQUESTED/AWAITING_PAYMENT.
- `/host`, `/host/bookings` and `/:bookingId`: existing Listing summaries, inbox,
  safe Owner/Pet information and explicit accept/decline actions. Non-host accounts
  receive onboarding. Milestone 12 adds Host setup, Listing editors and photos.

Request a Booking from Listing detail using the dates above the Pet selector.
Public availability uses its entered pet count; the real Booking uses the selected
Pet IDs, whose count may differ. Ineligible species are disabled. The server
revalidates active Pet ownership/species, dates, Listing state and capacity.
Only `listing_id`, `pet_ids`, `check_in`, `check_out` are submitted; the response
provides the authoritative subtotal, 10% fee and total. The website makes no price
estimate or payment request. Unknown submission outcomes must be checked in My
Bookings before retrying: the create endpoint has no idempotency-key contract.

TanStack Query holds server state under user-scoped private keys. Pet mutations
invalidate Pet collections (and archive refreshes Booking summaries). Booking
mutations invalidate Owner/Host collections/details and public availability/search.
Private caches are removed on logout or a detected expired session. There is no
background polling: use Refresh booking/inbox to observe another user's action.

### Optional login-enabled synthetic identities

The original `python -m app.scripts.seed_demo` remains a create-only marketplace
seed with 12 passwordless hosts. A separate opt-in command creates two additional
synthetic verified accounts, two Pets and one additional published Listing:

- Owner: `workflow.owner@pawtel.example.com` (Demo Milo, DOG; Demo Luna, CAT).
- Host: `workflow.host@pawtel.example.com`.
- Listing: **Demo workflow garden stay**, Norwood, SA; accepts dogs and cats.

These addresses use reserved example.com and pass the actual auth email validator.
No messages are delivered. For the password, choose your own local 15–128 character
passphrase. Set `PAWTEL_DEMO_PASSWORD` in the existing ignored root `.env` locally;
do not paste a password into tracked files, documentation, terminal history or a
chat. Alternatively, enter it without echo for just this command:

```zsh
cd ~/Desktop/PAWTEL/backend
source .venv/bin/activate
read -s 'PAWTEL_DEMO_PASSWORD?Local demo passphrase: '
export PAWTEL_DEMO_PASSWORD
python -m app.scripts.seed_workflow
unset PAWTEL_DEMO_PASSWORD
```

The command also reads the ignored `.env`. It refuses missing/invalid passwords,
non-development settings, remote/unsafe targets, wrong database/role identity and
superuser execution. It hashes through the normal Argon2id function, does not print
the password, creates no Bookings, and changes only the fixed synthetic login
identities. Rerunning is idempotent. Changing the configured password rotates
synthetic hashes and revokes their existing sessions. Existing Listing/Pet edits,
including archive state, are preserved; it is not a reset command. If you archive
the seeded Pets, create new Pets via the UI for subsequent demos. Normal
registration and verification requirements have no bypass or new endpoint.

### Manual walkthrough

1. Configure the local password and run the workflow seed as above. Optionally run
   the original marketplace seed as well if it has not already been run.
2. Start the backend:
   ```zsh
   cd ~/Desktop/PAWTEL/backend
   source .venv/bin/activate
   uvicorn app.main:app --reload
   ```
3. Start the frontend in another terminal:
   ```zsh
   cd ~/Desktop/PAWTEL/frontend
   npm run dev
   ```
4. Open http://localhost:5173 yourself. Log in as the synthetic Owner using your
   locally chosen password. Inspect My Pets; create/edit a spare Pet and archive
   it with confirmation; show archived Pets.
5. Search Norwood, open **Demo workflow garden stay**, choose future dates,
   optionally check availability, select Demo Milo and Demo Luna, and Request
   booking. Inspect Waiting for host and the server price snapshot in My Bookings.
6. Log out. Log in as the synthetic Host with the same locally configured password.
   Open Host workspace → Booking inbox → the request. Accept it. Create a second
   request if you also want to exercise decline; no decline reason is persisted.
7. Log out and return as Owner. Open My Bookings/detail and Refresh booking if
   needed. Confirm Payment required, total, deadline and temporarily reserved
   capacity. Use Pay securely for the Milestone 11 sandbox checkout, after configuring
   Stripe as described below.
8. Exercise cancellation on a separate requested/awaiting-payment Booking, empty
   inbox/filter states, keyboard navigation and mobile/tablet widths. Confirm no
   horizontal overflow and that price rows and actions remain readable.

Email delivery remains unconfigured. Normal newly registered users can manage
Pets, but require verified email for Bookings/hosting. Only the explicitly synthetic
local seed identities are marked verified by tooling. Never expose verification
tokens through the UI. Stripe frontend integration is documented below. Reviews,
messaging remain out of scope. Milestone 12 adds Listing management and uploads.

## Stripe Checkout Elements website (Milestone 11)

Owner AWAITING_PAYMENT detail now has **Pay securely**, leading to
`/account/bookings/:bookingId/pay`. The page reads the real Owner Booking, displays
its saved AUD prices/dates/Pets and loads Stripe's secure Elements form. It sends
no client price/status values. Card details stay in Stripe-controlled Elements.
Host pages have no checkout controls.

Set the sandbox's `VITE_STRIPE_PUBLISHABLE_KEY` privately in ignored root `.env`;
Vite reads root configuration but exposes only default VITE_-prefixed variables.
Keep backend STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET server-only. All keys
must belong to the same sandbox; this project intentionally refuses live keys.
Restart both servers after configuration changes. Empty `.env.example` placeholders
contain no working credentials.

For your manual local test, configure the Stripe CLI yourself and forward:

```zsh
stripe listen --events checkout.session.completed,checkout.session.expired --forward-to http://localhost:8000/api/v1/webhooks/stripe
```

Put that listener's signing secret privately in `.env` and restart the backend.
Keep STRIPE_RETURN_URL as `http://localhost:5173/checkout/return`; Stripe confirmation
uses a same-origin Booking-specific return path. Follow the Owner request/Host
acceptance demo above, return as Owner, choose Pay securely, load the form and use
only [Stripe's documented test scenarios](https://docs.stripe.com/testing).

The return page starts with **Checking payment status** and reads PAWTEL. It shows
success only when the backend returns CONFIRMED after a verified webhook. Pending
status checks stop after a bounded interval; manual refresh remains available.
Test a decline/retry, cancellation, logout, stale checkout URLs and mobile widths
manually. No real sandbox payment was performed by automation.

Checkout client secrets stay in component memory, outside Query/Mutation caches,
URLs, logs and browser storage. Reloads use the protected backend endpoint again.
The only backend compatibility change replaces the removed Endive creation input
`payment_method_types` with `allowed_payment_method_types`, preserving card-only
Elements Checkout. No Booking/webhook/security rules were changed. See
[the complete payment walkthrough and lifecycle notes](docs/payments.md#owner-checkout-elements-website-milestone-11).

## Host onboarding, Listing management and photos (Milestone 12)

Hosts can now demonstrate the product with their own Listings: `/host` offers
**Become a Host** for an eligible account without HostProfile, or a workspace with
bio editing, Listing summary and Booking inbox. `/host/listings` lists owned
Listings; create a draft at `/host/listings/new` and edit at
`/host/listings/:listingId/edit`. Publish, move to draft and confirmed archive use
the existing lifecycle. Archived Listings are read-only and Booking history stays.

AUD inputs convert decimal strings to exact integer cents. Configure DOG/CAT
species, location, capacity and prices. Drafts can omit species; publication needs
at least one. Capacity is simultaneous Pets; existing reservations constrain
reductions. Hosts do not set PAWTEL's service fee. Location fields do not imply
geocoding or geographic validation.

Cloudinary provides Listing media through authenticated backend uploads. Add
CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET privately to
ignored root `.env`; never add VITE_ prefixes. Install updated backend dependencies
and run `python -m alembic upgrade head` before starting the backend. No provider
credentials are configured by the application or required for normal automated
tests. Without them, drafts/Listing management and seeded placeholders still work.

Save a draft before adding photos. Up to six JPEG/PNG/WebP images are supported,
5 MiB each, 200–6000 pixels per side, maximum 24 megapixels, non-animated. The server
checks decoded bytes and strips metadata. Upload/preview, reorder using explicit
buttons, and remove in the editor. The first photo becomes the public card cover;
detail shows the gallery. No photos or failed delivery uses labelled placeholders.
External provider/DB failures retain tracked cleanup state; use
`python -m app.media.cleanup` in the configured backend to retry cleanup. See the
[Host/media setup and failure guide](docs/host-listings.md#host-website-and-listing-media-milestone-12)
and [media ADR](docs/adr/0008-cloudinary-listing-media.md).

Manual walkthrough (you perform browser actions):

1. Start backend and frontend as above; privately configure Cloudinary for actual
   photo testing. Existing demo Host can log in, or use a verified account without
   HostProfile and choose Become a Host. Normal unverified accounts still require
   verification; email delivery is not implemented.
2. Create a Listing and leave it Draft. Edit description/location, AUD prices,
   simultaneous capacity and DOG/CAT selection. Confirm it is not public yet.
3. Upload photos, inspect preview/alt text, change cover order and remove a spare
   photo. Check visible errors for invalid format/oversize or missing provider setup.
4. Publish, log out, search the chosen suburb, inspect the card cover and gallery.
5. Return as Host; move to draft and republish if desired. Confirm archive, log out
   and verify public search/detail no longer expose the Listing.
6. Resize desktop/tablet/mobile and keyboard-test forms, confirmations and photo
   move/remove controls. No automated browser or screenshot verification was used.

No real cloud upload was performed by the automated test suite. Storage credentials,
provider/CDN behavior and visual review require your manual verification. Existing
seed Listings intentionally keep their deterministic SVGs without cloud assets.

# PAWTEL interview revision guide

Suggested spoken material for Victor: adapt it to your own understanding and avoid
claiming operational experience that has not happened. Use the [case study](portfolio-case-study.md)
for details and the [README](../README.md) for current test counts.

## 60-second explanation

“PAWTEL is my Australian pet-boarding marketplace portfolio project. Owners can
browse stays, manage Pets and request a Booking. The same User account can enable
Host mode, manage Listings and accept or decline requests. I built it with React,
TypeScript, FastAPI and PostgreSQL. The interesting part is correctness: the server
owns prices and identity, acceptance rechecks capacity under database locks, and
signed Stripe webhooks—not the browser—confirm payment. Cloudinary stores photos
while PostgreSQL tracks media states and cleanup. GitHub CI now passes backend,
frontend and real UI/API/database E2E checks. I’ve prepared a same-origin Render
deployment, but I haven’t claimed a live release or production readiness.”

## Three-minute deeper explanation

“I deliberately kept the scope to boarding for dogs and cats. I wanted one complete
journey rather than unrelated feature demos: search a Listing, choose owned Pets,
request dates, have the Host accept, then use Stripe sandbox checkout.

The frontend uses React Router and TanStack Query. Query invalidation updates
Booking collections/details after mutations, and logout clears private data. The
backend derives User identity from an opaque cookie session; the database stores
the session hash and Argon2id password hashes. Pydantic contracts reject fields the
client shouldn’t own. Owner-scoped queries protect private Pets and Bookings, while
Host scope protects Listing management. Authenticated writes use CSRF protection.

For capacity, public availability is only advisory. Two requests can compete after
both saw available space. Host acceptance locks the parent Listing, then the
Booking, and rechecks overlapping occupancy inside the transaction. That protects
the final space, while the server persists an integer-cent quote snapshot. I tested
the race with separate PostgreSQL connections, rather than mocking a lock.

External services introduce different failure modes. Stripe Checkout creation can
time out after succeeding, so there’s a durable payment attempt and idempotency key.
Webhooks are signed and deduplicated before changing eligible Booking state. A late
payment cannot resurrect a cancelled stay. Cloudinary also cannot join a SQL
transaction, so upload/delete states and compensating cleanup track partial results.

The first real CI run exposed configuration leaking from CI environment variables
into test fixtures. Production validation was correct; I fixed the fixtures and
reproduced CI-style settings locally. The subsequent GitHub run passed all jobs.
The selected deployment serves React and FastAPI from one origin to preserve
host-only SameSite=Lax cookies. It has explicit migrations and readiness checks.
Remaining work includes manual deployment/provider verification, real email,
monitoring, shared abuse controls and restore/security/load exercises.”

## Architecture

Explain Browser → React → FastAPI → PostgreSQL first. Add Stripe's inbound signed
webhook and Cloudinary's public image delivery. Routers validate contracts, services
own transactions, models/constraints persist state and adapters isolate providers.
One modular monolith is proportionate; there is no need to claim microservices.

## Security

A URL's resource ID does not establish ownership. Session identity scopes queries;
frontend guards help navigation, not authorization. Secure HttpOnly host-only cookies,
exact Origin/CORS checks and synchronizer CSRF protect writes. Passwords/session
credentials and Checkout client secrets stay out of browser persistence and logs.

## Booking concurrency

Say which rows lock and why: Listing first, then Booking, recheck within the
transaction. READ COMMITTED lets the next acceptor observe the preceding commit.
Availability does not reserve; AWAITING_PAYMENT holds capacity under actual rules.
Do not substitute a frontend availability button for a transaction guarantee.

## Stripe

Elements controls card inputs. The frontend starts checkout without amounts and
keeps client_secret transient. Provider calls happen outside long DB locks. The
signed event receipt, attempt, amount/currency and Booking eligibility determine
confirmation. Browser return polling only observes the backend. Late money becomes
reconciliation; payouts/refunds beyond existing behavior are not implemented.

## Cloudinary failures

PostgreSQL stores metadata, ordering and states; Cloudinary holds image bytes.
Public DTOs expose safe ready media. If upload succeeds but association fails,
cleanup/compensation must account for the asset. Deletion can also fail. Explain
those intermediate states instead of claiming an impossible shared transaction.

## Testing and CI

Differentiate unit/component, migrated PostgreSQL integration, real separate-connection
concurrency and headless E2E. Normal CI uses fake providers, not fake internal API
requests. Cite [the successful run](https://github.com/doyosogo/Pawtel/actions/runs/43312304584)
for `a8faa4f`; do not treat future changes as remotely verified until their own run passes.

## Deployment

One Render HTTPS origin serves SPA/API, plus same-region managed PostgreSQL, keeping
SameSite=Lax cookie behavior simple. A release hook runs Alembic; startup verifies
schema. TLS requirements, small pools, request IDs, safe logs and readiness help
operation. Readiness failure can trigger platform restarts. No actual public URL,
paid resource or real sandbox/provider smoke success is claimed.

## Current limitations and next steps

Finish the [manual deployment handoff](deployment-checklist.md) first. Real service
launch would need email/recovery, customer/privacy/support processes, shared abuse
controls, retention/maintenance scheduling, backup restore drills and security/load
review. Final CSP and provider settings need real deployed verification. Scope
expansion should follow evidence; reviews/messaging/notifications are not implemented.

## Technical STAR stories

### 1. Competing reservations

- **Situation:** Two requested stays can compete for the same final Pet capacity.
- **Task:** Prevent accepted bookings from exceeding capacity despite stale clients.
- **Action:** Lock Listing then Booking, recheck occupancy transactionally, and test
  competing acceptors using real separate PostgreSQL connections.
- **Result:** Tests demonstrate a single final-space winner and clear conflict handling;
  no invented production traffic/performance claim.

### 2. Payment authority

- **Situation:** Browser returns are untrusted and Stripe can repeat event delivery.
- **Task:** Confirm only valid paid bookings once, including cancellation races.
- **Action:** Persist attempts/idempotency keys and signed event receipts, validate
  pricing/state and reconcile late payment instead of resurrecting a Booking.
- **Result:** Deterministic tests cover duplicate events, uncertain outcomes and late
  payment; no live-money or automatic refund claim.

### 3. Media partial failure

- **Situation:** An uploaded Cloudinary asset and SQL association can succeed separately.
- **Task:** Avoid presenting broken media or silently losing cleanup responsibility.
- **Action:** Keep durable media states, safe public projections and compensating
  delete/retry paths, tested with fake-provider and DB-failure cases.
- **Result:** Failures remain visible/recoverable rather than falsely atomic.

### 4. CI environment leakage

- **Situation:** Local checks passed but the first GitHub backend job failed.
- **Task:** Reproduce the difference without weakening production safety.
- **Action:** Export CI-style database variables, identify inherited settings in
  production/no-database fixtures and explicitly isolate those settings.
- **Result:** Local reproduction passed and the next GitHub-hosted workflow passed
  backend, frontend and E2E. Production refusal remained intact.

### 5. Cookie-aware deployment

- **Situation:** Separate provider origins complicate secure session cookies and CSRF.
- **Task:** Prepare a practical portfolio deployment without unnecessary domain/proxy work.
- **Action:** Choose one service origin for compiled React and FastAPI, preserve
  SameSite=Lax/host-only cookies and document explicit origins, migrations and probes.
- **Result:** The Blueprint/schema and local HTTP smoke checks pass; account setup and
  actual public verification remain manual, not an invented deployment outcome.

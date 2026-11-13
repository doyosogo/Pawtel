# PAWTEL portfolio case study

## Problem

Pet Owners need to find suitable boarding, understand dates and prices, and request
care from a Host. Hosts need to control Listings and decide which requests they
can actually accommodate. The technical challenge is maintaining trustworthy
identity, capacity and payment state as different people act concurrently.

## Scope

PAWTEL is Victor's Australian dog/cat **boarding-only** portfolio MVP. It implements
public discovery, private Pets, optional Host mode, Listing/media management,
Booking requests and Stripe sandbox payment. Australian states/postcodes and AUD
are explicit assumptions; suburb/postcode pairing is not geocoded validation.

There are no invented reviews, amenities, distances or service categories. It does
not provide real boarding or process live payments. The [public frontend showcase](frontend-showcase.md#hosted-verification) is live
and verified. It removes infrastructure/login barriers for recruiters through
explicitly synthetic data and simulated actions. Full-stack behavior is separately
evidenced by tests/CI; the Render full-stack deployment is not live.

## Architecture

React/TypeScript provides a responsive marketplace and separate Owner/Host views.
TanStack Query manages server state; the API remains authoritative. FastAPI exposes
explicit Pydantic contracts, focused services own transactions, and PostgreSQL
provides relational constraints and locks through SQLAlchemy/Psycopg. Alembic owns
DDL. This modular monolith keeps cross-domain changes inspectable without adding
microservice or distributed-message infrastructure.

Stripe and Cloudinary have explicit server adapter boundaries. The selected Render
layout serves the compiled SPA and API from one HTTPS origin, simplifying secure
cookie behavior. See the [architecture diagram](architecture.md) and [ADRs](adr/README.md).

## Key engineering challenges

### Sessions and authenticated writes

An opaque session credential lives in an HttpOnly cookie; PostgreSQL stores its
hash. Passwords use Argon2id. Production cookies are Secure and host-only. Exact
Origin/custom-header checks and a synchronizer CSRF token protect writes.
Expired/revoked sessions are rejected; logout clears private frontend queries.
Credentials never belong in browser storage or request logs.

### Ownership and IDOR prevention

A supplied Pet/Listing/Booking ID is not permission. Services scope resources to
the authenticated User/Host, derive ownership server-side and expose explicit safe
DTOs. Missing and foreign private resources share safe not-found behavior. A User
can optionally host without creating a second account model.

### Booking races and capacity

Public availability is a snapshot, not a reservation. Two Hosts' actions on requests
for one Listing can race even when both clients saw available space. Acceptance
locks the Listing first, then the Booking, and rechecks overlapping Pet occupancy
inside the transaction at READ COMMITTED. AWAITING_PAYMENT reserves capacity under
the established lifecycle; requests alone do not. Real separate-connection database
tests verify one winner for the final space and the lock protocol.

### Authoritative price snapshots

The client submits Listing ID, dates and selected Pet IDs—not ownership, status or
totals. The server validates eligibility, calculates integer AUD cents and persists
the accommodation/service-fee/total snapshot. The frontend displays the returned
values. This avoids treating a browser estimate as an authoritative quote.

### Stripe webhook authority and uncertain outcomes

Stripe-controlled Checkout Elements handles payment inputs. A browser redirect
cannot prove payment. Verified raw-body signed webhooks match durable attempts,
amount/currency and Booking state; event receipts deduplicate delivery. Persisted
attempts and idempotency keys make a timed-out Checkout call recoverable. A late
payment after cancellation becomes reconciliation rather than a falsely confirmed,
unreserved stay. Automatic refunds and Host payouts are deliberately out of scope.

### Cloudinary/database partial failure

Cloudinary cannot join a normal PostgreSQL transaction. Durable upload/delete states
and cleanup track uncertainty when storage succeeds but DB association fails, or
provider deletion fails. Public responses show safe ready media only; metadata and
ordering live in PostgreSQL, image bytes do not. Synthetic Listings retain tasteful
fallback illustrations without requiring provider access.

### CI/E2E and deployment hardening

Local checks initially passed, but the [first GitHub run](https://github.com/doyosogo/Pawtel/actions/runs/43130211923)
failed in the backend job. CI exported database configuration. Two production-shaped
fixtures inherited TEST_DATABASE_URL, and a no-database readiness test inherited
DATABASE_URL. Production validation correctly rejected unsafe settings; it was not
the defective component. `_env_file=None` had not isolated process environment.

The fixtures were made explicit. CI-style local reproduction then passed without
weakening validation, database guards or security. The next run for current `main`,
[43312304584](https://github.com/doyosogo/Pawtel/actions/runs/43312304584), completed
**success** on GitHub-hosted Linux for backend, frontend and E2E at commit `a8faa4f`.
This is verified remote evidence, not an inference from local tests. New commits
still need their own CI result.

Isolated E2E crosses the real React/API/PostgreSQL boundary. Safe JSON events and
request IDs support diagnosis without logging secrets. Readiness checks DB/schema;
production startup refuses unsafe configuration. Explicit pre-deploy migrations,
same-origin cookies and private invited demo accounts define a practical deployment
boundary. A green suite is not proof of a deployed or production-ready service.

## Trade-offs

- One application/database and direct focused services, rather than premature
  microservices, Redis or a generic repository framework.
- Opaque database sessions rather than introducing JWT refresh-token machinery.
- A small number of real E2E journeys, with detailed failures tested below the UI.
- Provider fakes in automated tests; real sandbox/CDN verification remains separate.
- Same-origin SPA/API deployment rather than two free domains with cross-site cookies;
  the trade-off is no separate global frontend CDN.
- Single-process demo budgets with explicit limits, not a false distributed limiter.
- Operator-reviewed maintenance rather than an unauthenticated reset or destructive
  automatic cleanup of payment/media history.

## Testing strategy

Unit tests cover validation, prices, provider parsing and operational rules. React
component/API-helper tests cover forms, statuses, errors, session behavior and mocked
Stripe boundaries. Migrated PostgreSQL integration tests cover ownership, persistence,
state transitions, signatures/deduplication, failure recovery and genuine lock races.
Headless E2E verifies Owner request → Host acceptance → Owner AWAITING_PAYMENT, plus
Pet creation and Listing publication. It does not intercept internal APIs or require
Stripe/Cloudinary credentials. See [current counts and commands](../README.md#tests-and-ci).

## Current limitations

No public release has been verified. Email delivery/recovery, customer support,
privacy/legal/retention procedures, shared abuse protection, operational scheduling,
final restrictive CSP, backup restore drills and security/load assessment remain
launch work. Payments are test-only. No reviews, messaging, notifications, admin,
Connect/payouts or maps were added. Existing development-tooling advisories are
tracked honestly; Python dependency consistency is not a vulnerability audit.

## What I learned

Suggested discussion points for Victor to adapt to his own experience:

- State what the server can prove: availability is advisory, payment returns are
  observations, and authorization derives from session identity.
- Put correctness at the transaction boundary. A disabled button cannot prevent
  concurrent reservations, foreign IDs or client-edited totals.
- Design for partial failure before making external calls. Durable attempts/states
  and recovery paths matter more than a happy-path provider response.
- Reproduce the execution environment. The CI incident showed that a test can
  accidentally depend on local configuration even when its own code looks explicit.
- Choose deployment topology around authentication and operational constraints,
  rather than accumulating hosting providers for presentation value.

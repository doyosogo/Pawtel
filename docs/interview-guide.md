# PAWTEL interview revision guide

Suggested spoken material for Victor: adapt it to your own understanding and
avoid claiming operational experience that has not happened. Use the
[case study](portfolio-case-study.md) for details and the [README](../README.md)
for current test counts.

## 60-second explanation

“PAWTEL is my Australian pet-boarding marketplace portfolio project. Owners can
browse stays, manage Pets and request a Booking. The same User account can
enable Host mode, manage Listings and accept or decline requests. I built it
with React, TypeScript, FastAPI and PostgreSQL. The interesting part is
correctness: the server owns prices and identity, acceptance rechecks capacity
under database locks, and signed Stripe webhooks—not the browser—confirm
payment. Cloudinary stores photos while PostgreSQL tracks media states and
cleanup. GitHub CI now passes backend, frontend and real UI/API/database E2E
checks. The public Vercel showcase reuses that interface with synthetic data so
reviewers can explore without setup. The full-stack Render path is prepared but
not live; this is a portfolio MVP.”

## Three-minute deeper explanation

“I deliberately kept the scope to boarding for dogs and cats. I wanted one
complete journey rather than unrelated feature demos: search a Listing, choose
owned Pets, request dates, have the Host accept, then use Stripe sandbox
checkout.

The frontend uses React Router and TanStack Query. Query invalidation updates
Booking collections/details after mutations, and logout clears private data. The
backend derives User identity from an opaque cookie session; the database stores
the session hash and Argon2id password hashes. Pydantic contracts reject fields
the client shouldn’t own. Owner-scoped queries protect private Pets and
Bookings, while Host scope protects Listing management. Authenticated writes use
CSRF protection.

For capacity, public availability is only advisory. Two requests can compete
after both saw available space. Host acceptance locks the parent Listing, then
the Booking, and rechecks overlapping occupancy inside the transaction. That
protects the final space, while the server persists an integer-cent quote
snapshot. I tested the race with separate PostgreSQL connections, rather than
mocking a lock.

External services introduce different failure modes. Stripe Checkout creation
can time out after succeeding, so there’s a durable payment attempt and
idempotency key. Webhooks are signed and deduplicated before changing eligible
Booking state. A late payment cannot resurrect a cancelled stay. Cloudinary also
cannot join a SQL transaction, so upload/delete states and compensating cleanup
track partial results.

The first real CI run exposed configuration leaking from CI environment
variables into test fixtures. Production validation was correct; I fixed the
fixtures and reproduced CI-style settings locally. The recovery passed all jobs.
A later showcase CI failure was a browser-cache mismatch: install and test
looked in different directories. A clean reproduction exposed it, and one
job-level environment setting aligned them without skipping tests.

The live Vercel showcase is deliberately separate. It uses the same components
with an in-memory data adapter, synthetic personas and no API/provider traffic.
It helps a recruiter explore the product; it does not prove database or payment
behavior. The full-stack deployment is prepared for one Render origin to keep
session cookies straightforward, with explicit migrations/readiness. That
deployment is not live. Real email, hosted provider acceptance, shared abuse
controls, monitoring and restore/security/load exercises remain work before a
real service launch.”

## Architecture

Explain Browser → React → FastAPI → PostgreSQL first. Add Stripe's inbound
signed webhook and Cloudinary's public image delivery. Routers validate
contracts, services own transactions, models/constraints persist state and
adapters isolate providers. One modular monolith is proportionate; there is no
need to claim microservices.

## Security

A URL's resource ID does not establish ownership. Session identity scopes
queries; frontend guards help navigation, not authorization. Secure HttpOnly
host-only cookies, exact Origin/CORS checks and synchronizer CSRF protect
writes. Passwords/session credentials and Checkout client secrets stay out of
browser persistence and logs.

## Booking concurrency

Say which rows lock and why: Listing first, then Booking, recheck within the
transaction. READ COMMITTED lets the next acceptor observe the preceding commit.
Availability does not reserve; AWAITING_PAYMENT holds capacity under actual
rules. Do not substitute a frontend availability button for a transaction
guarantee.

## Stripe

Elements controls card inputs. The frontend starts checkout without amounts and
keeps client_secret transient. Provider calls happen outside long DB locks. The
signed event receipt, attempt, amount/currency and Booking eligibility determine
confirmation. Browser return polling only observes the backend. Late money
becomes reconciliation; payouts/refunds beyond existing behavior are not
implemented.

## Cloudinary failures

PostgreSQL stores metadata, ordering and states; Cloudinary holds image bytes.
Public DTOs expose safe ready media. If upload succeeds but association fails,
cleanup/compensation must account for the asset. Deletion can also fail. Explain
those intermediate states instead of claiming an impossible shared transaction.

## Hardest technical challenge

“The hardest part was preserving Booking correctness when people and providers
act at different times. An availability result can be stale, acceptance can race
another acceptance, and a payment can arrive after cancellation. I made the
server own each transition, used Listing-first locks for capacity, and treated
late provider results as reconciliation rather than permission to overwrite
state. The evidence is tests with separate database connections and
fake-provider failure cases, not a claim of production traffic.”

## Testing and CI

Differentiate component, migrated PostgreSQL integration, separate-connection
concurrency and headless E2E tests. Provider adapters are faked in normal CI;
the real full-stack E2E still crosses React → FastAPI → PostgreSQL. The static
showcase suite proves a different boundary: UI exploration with no
backend/provider traffic.

There are two useful CI stories. First, CI database variables leaked into
fixtures that needed isolated production-style settings. Production refusal was
correct; explicit fixture configuration fixed the tests. Later, Chromium
installed into the default cache while showcase tests expected the project
cache. Fresh installation reproduced the missing executable; job-level
`PLAYWRIGHT_BROWSERS_PATH` aligned both. Tests remained enabled. Use the
[README](../README.md) for the current verified run, not an older successful
commit as evidence for future changes.

## Vercel showcase architecture

“A recruiter can open the public showcase immediately. A Vite mode and public
flag select a closed in-memory adapter behind the existing typed client, so most
pages are shared with real mode. Persona switching is UI state, not an auth
bypass. No FastAPI change was needed. Payment and cloud uploads are explicitly
disabled, and hosted tests observed actual traffic without request mocking.
Refresh resets the synthetic data. This proves interface exploration; full-stack
tests prove server rules separately.”

## Deployment trade-offs

Vercel serves the static showcase, while the real system is prepared for one
Render HTTPS origin serving SPA/API plus same-region managed PostgreSQL.
Same-origin keeps host-only SameSite=Lax cookies simpler; the trade-off is less
separation/CDN flexibility. A release hook runs Alembic and startup verifies
schema. TLS requirements, small pools, request IDs, safe logs and readiness
support operation. Readiness failure can trigger platform restarts. The Vercel
public URL is verified; Render and real provider acceptance are still manual. Do
not describe one as proof of the other.

## Current limitations and next steps

The public frontend showcase is live; full-stack Render is not. Email delivery
and recovery are absent; Stripe is sandbox-only; Cloudinary hosted acceptance is
pending. Real service launch needs stronger shared abuse controls, monitoring,
maintenance, restore drills, provider/security/load verification and
customer/privacy/support processes. Optional full-stack deployment follows the
[manual handoff](deployment-checklist.md); no new feature is required to present
the portfolio. Reviews, messaging, notifications and admin are outside the
current scope.

## Technical STAR stories

### 1. Competing reservations

- **Situation:** Two requested stays can compete for the same final Pet
  capacity.
- **Task:** Prevent accepted bookings from exceeding capacity despite stale
  clients.
- **Action:** Lock Listing then Booking, recheck occupancy transactionally, and
  test competing acceptors using real separate PostgreSQL connections.
- **Result:** Tests demonstrate a single final-space winner and clear conflict
  handling; no invented production traffic/performance claim.

### 2. Payment authority

- **Situation:** Browser returns are untrusted and Stripe can repeat event
  delivery.
- **Task:** Confirm only valid paid bookings once, including cancellation races.
- **Action:** Persist attempts/idempotency keys and signed event receipts,
  validate pricing/state and reconcile late payment instead of resurrecting a
  Booking.
- **Result:** Deterministic tests cover duplicate events, uncertain outcomes and
  late payment; no live-money or automatic refund claim.

### 3. Media partial failure

- **Situation:** An uploaded Cloudinary asset and SQL association can succeed
  separately.
- **Task:** Avoid presenting broken media or silently losing cleanup
  responsibility.
- **Action:** Keep durable media states, safe public projections and
  compensating delete/retry paths, tested with fake-provider and DB-failure
  cases.
- **Result:** Failures remain visible/recoverable rather than falsely atomic.

### 4. CI environment leakage

- **Situation:** Local checks passed but the first GitHub backend job failed.
- **Task:** Reproduce the difference without weakening production safety.
- **Action:** Export CI-style database variables, identify inherited settings in
  production/no-database fixtures and explicitly isolate those settings.
- **Result:** Local reproduction passed and the next GitHub-hosted workflow
  passed backend, frontend and E2E. Production refusal remained intact.

### 5. Cookie-aware deployment

- **Situation:** Separate provider origins complicate secure session cookies and
  CSRF.
- **Task:** Prepare a practical portfolio deployment without unnecessary
  domain/proxy work.
- **Action:** Choose one service origin for compiled React and FastAPI, preserve
  SameSite=Lax/host-only cookies and document explicit origins, migrations and
  probes.
- **Result:** The Blueprint/schema and local HTTP smoke checks pass; account
  setup and actual full-stack public verification remain manual; the separately
  live Vercel showcase does not prove that deployment.

### 6. Showcase browser-cache failure

- **Situation:** The showcase passed locally but failed at browser launch on
  fresh CI.
- **Task:** Reproduce the failure without dropping the new showcase tests.
- **Action:** Use fresh dependencies/home/browser state, identify default-cache
  versus project-cache paths, then set the browser path at frontend job scope.
- **Result:** Clean reproduction passed after the fix and the pushed GitHub run
  was green. The lesson was to test installation and execution together, not
  just reuse a developer browser cache.

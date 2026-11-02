# Pre-payment Booking workflow (Milestone 7)

PAWTEL now supports requests, Host review/accept/decline and Owner pre-payment
cancellation. There is no Stripe integration, payment-success endpoint, automatic
expiry or completion. AWAITING_PAYMENT is the last successful acceptance state here.

## API and permissions

All endpoints require the existing authenticated, active, email-verified User
dependency. Every POST requires JSON, X-PAWTEL-Request: 1, an allowed Origin when
supplied, and the session X-CSRF-Token. Actions send `{}`; unknown action fields are
rejected. No arbitrary status PATCH or client-supplied quote/owner/Host exists.

| Method/path | Meaning |
| --- | --- |
| POST /api/v1/bookings | 201 creates own REQUESTED request and price snapshot |
| GET /api/v1/bookings | Own bookings only |
| GET /api/v1/bookings/{id} | Own booking detail |
| POST /api/v1/bookings/{id}/cancel | Own REQUESTED/AWAITING_PAYMENT to CANCELLED; repeat CANCELLED is unchanged 200 |
| GET /api/v1/host/bookings | Bookings for caller's Listings only |
| GET /api/v1/host/bookings/{id} | Detail for caller's Listing only |
| POST /api/v1/host/bookings/{id}/accept | REQUESTED to AWAITING_PAYMENT if revalidation succeeds |
| POST /api/v1/host/bookings/{id}/decline | REQUESTED to DECLINED |

Collections return arrays ordered created_at descending then UUID descending, with
optional status, limit (default 20, maximum 50) and nonnegative offset. No total count
or snapshot pagination is claimed. Non-hosts see an empty incoming collection;
direct missing/foreign resources share 404 booking_not_found. Ownership is included
in SQL: owner_id for Owner routes, Listing.host_id for Host routes.

Responses explicitly expose dates, state, snapshot breakdown, deadline/timestamps,
Listing id/title/suburb/state, Owner display name and only the selected Pet summaries
(id/name/species/breed/date_of_birth/active). They never expose emails, User ownership
IDs, credentials, authentication relationships or unrelated Pets. Pet/Listing text
is current profile data, not a historical snapshot; price fields are snapshots.
Having a booking gives its Listing Host access to those selected Pet details, even
if a Pet is subsequently archived. No separate User profile endpoint is introduced.

Example request body (IDs are placeholders):

```json
{"listing_id":"00000000-0000-0000-0000-000000000001",
 "pet_ids":["00000000-0000-0000-0000-000000000002"],
 "check_in":"2027-11-10","check_out":"2027-11-13"}
```

## Request validation and retries

Listing must currently be PUBLISHED; draft/archived/missing share listing_unavailable.
Self-booking is rejected. At least one, at most 100 distinct Pet IDs are accepted
(the upper bound limits request payload/work, not a new Listing capacity rule).
Pets must all be active and belong to the caller, and their species must be accepted.
Foreign/missing/archived pets share pet_not_available without revealing private
existence. Number of pets must fit configured and currently available capacity.
REQUESTED rows do not reserve, so competing requests may coexist.

Dates use half-open [check_in, check_out), with checkout strictly later. Check-in
must be today or later by **UTC calendar date**. This is deterministic and temporary:
PAWTEL does not yet have per-Listing timezones, so it is not local Australian midnight
validation. Acceptance repeats this check if a request has become stale. Request-time
availability is advisory and may change immediately; acceptance is authoritative.

POST /bookings is **not idempotent**. Repeating it may create another request. Do not
blindly retry after an unknown outcome: inspect own bookings first. Request-idempotency
hardening is separate from mandatory future payment/webhook idempotency.

## Exact pricing and snapshots

All monetary values are integer AUD cents. The server reads Listing configuration:

```text
nights = checkout - checkin
subtotal = nights * (base + additional * (pet_count - 1))
fee = 10% of subtotal, rounded to nearest cent HALF-UP
total = subtotal + fee
```

For nonnegative cents, `(subtotal + 5) // 10` exactly implements HALF-UP for the fee;
no float or custom cryptographic/money framework is involved. 5 cents gives a 1-cent
fee; 4 gives zero; 15 gives 2. Three nights with base 5000, additional 2000 and two
pets produce subtotal 21000, fee 2100, total 23100 cents. Free configuration remains
valid. Inputs and final quote are bounded to JavaScript-safe integer values, well
within BIGINT; oversized quotes fail booking_price_out_of_range rather than overflow.

Existing Booking columns retain base/additional nightly rates, subtotal, fee and
total. Listing changes do not reprice requests. Acceptance preserves the submitted
quote; no implicit requote is allowed. Future explicit requoting/payment policy may
address long-lived requests. No fees are calculated in route handlers or clients.

## State transitions and payment deadline

A focused service owns the explicit transition mapping. Implemented:
new → REQUESTED; REQUESTED → DECLINED/AWAITING_PAYMENT/CANCELLED;
AWAITING_PAYMENT → CANCELLED. CANCELLED cancellation is an idempotent unchanged 200.
Repeated accept/decline and other invalid states return 409 booking_invalid_state.
No payment/confirmed/failed/expired/completed transition is exposed.

Acceptance sets timezone-aware payment_expires_at to current UTC time plus
BOOKING_PAYMENT_WINDOW_SECONDS (default 1800; permitted 60–86400). The deadline is
not a scheduler. Even overdue AWAITING_PAYMENT rows keep reserving until explicitly
cancelled or a later payment/expiry service transitions them. Cancellation clears
the actionable payment deadline; no payment/refund operation exists.

## Transaction and capacity protocol

Services own explicit db.begin/commit/rollback boundaries. Request creation inserts
Booking plus BookingPet associations atomically; prices are calculated within that
transaction. No reservation is acquired by creating REQUESTED.

Every implemented action (accept, decline, cancel) uses this ordering:

1. Begin transaction at PostgreSQL READ COMMITTED, explicitly configured on the
   application and test engines so deployment defaults cannot silently change it.
2. Resolve Listing identity through an ownership-scoped Booking query.
3. SELECT Listing FOR UPDATE; Host actions additionally scope Host identity.
4. Reload and lock the owned Booking FOR UPDATE, then check current state.
5. For acceptance: require PUBLISHED Listing, eligible active/verified Owner,
   non-stale dates, active owned Pets, accepted species and current per-night capacity.
6. Reuse Milestone 6's clipped-event/window-sum occupancy query, restricted to this
   Listing. Count AWAITING_PAYMENT/CONFIRMED only. Reject if any night would overflow.
7. Apply the allowed transition/deadline, flush and commit. Any failure rolls back.

The stable Listing row coordinates even an empty reservation set. A waiter sees the
prior accepter's committed reservation when its later capacity statement runs at
READ COMMITTED. Booking is always locked AFTER Listing, including cancellation out
of AWAITING_PAYMENT. REQUESTED cancellation/decline conservatively follow that same
order even though no inventory release is needed. Ordinary public searches never
lock or reserve and cannot guarantee acceptance.

No network/provider work runs under these locks. Lock waits are bounded to five
seconds; lock timeout/deadlock/serialization OperationalErrors roll back and become
safe 409 booking_busy. The server does not automatically replay commands; reload
before retrying a stateful action. Capacity conflicts return 409
booking_capacity_unavailable and leave the request/deadline unchanged.

Existing Listing configuration UPDATEs already acquire the parent write lock. A
capacity change now checks peak current reserved occupancy while holding that lock;
a reduction below any AWAITING_PAYMENT/CONFIRMED reservation returns 409
listing_capacity_reserved and rolls back all accompanying fields/species. This
prevents a later edit from invalidating accepted capacity. It conservatively includes
all reserving dates, even stale holds; no automatic cleanup is implied. Archiving
preserves existing reservations, prevents new requests/acceptance and permits Owner
cancellation. Reserved Booking dates/pets have no edit API.

Future confirmation/failure/expiry/refund flows and every capacity writer must obey
the same Listing-first protocol. It is application-owned coordination, not protection
against arbitrary direct SQL. Coarse per-Listing serialization may limit hot-listing
throughput. No Redis/distributed lock, queues or scheduler is necessary now.

## Database boundary, tests and limitations

No migration/index change was needed. PostgreSQL enforces FKs, unique BookingPet
pairs, ordered dates, valid enum states, nonnegative snapshots, total=subtotal+fee,
and a deadline for AWAITING_PAYMENT. It does not enforce HTTP ownership, selected-Pet
ownership, legal transitions, fee formula, self-booking prohibition or concurrent
aggregate capacity. Those belong to transactional services.

API tests cover permission/privacy, all request rules, snapshots, transitions,
deadlines, release, revalidation, CSRF, parent-capacity edits and rollback failures.
Real concurrency tests use independently committed synthetic rows and separate
connections. The first accepter holds the Listing lock, the second starts concurrently,
and an observer verifies pg_blocking_pids before allowing the first to commit. Exactly
one request succeeds and the loser remains REQUESTED without a deadline. Cases cover
capacity one, and capacity three with one pre-existing reserved pet and two competing
two-pet requests. No sleep-based scheduling assumption is used. Finally cleanup removes
only fixture UUIDs on the protected test DB; normal API tests retain rollback isolation.

Remaining: Stripe initiation, signed webhooks/idempotency, payment/booking consistency,
expiry, confirmed cancellations/refunds, completion, notifications, booking UI, request
idempotency and real load/lock-contention measurements. Pet/account edits concurrent
with acceptance are not a versioned profile-snapshot workflow; later Host-review policy
may require stronger immutable profile/version semantics. Existing authentication
rate-limit/deployment limitations still apply.

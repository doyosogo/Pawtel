# Booking state machine

Milestone 7 implements request creation, Host accept/decline and Owner cancellation
from REQUESTED/AWAITING_PAYMENT. Payment transitions and automatic completion below
remain future design. PostgreSQL validates enum membership and row constraints, not
old-to-new transitions. See [Booking API](bookings.md) for implemented contracts.

| Current | Next | Responsible actor / condition | Capacity effect |
|---|---|---|---|
| REQUESTED | DECLINED | Listing host declines the request | None reserved |
| REQUESTED | CANCELLED | Owner withdraws request | None reserved |
| REQUESTED | AWAITING_PAYMENT | Host accepts after all transactional checks | Reserve all pets for each stay night |
| AWAITING_PAYMENT | CONFIRMED | Future payment service validates successful payment before deadline | Retain reservation |
| AWAITING_PAYMENT | PAYMENT_FAILED | Future payment service records definitive payment failure | Release reservation |
| AWAITING_PAYMENT | EXPIRED | System observes payment deadline elapsed | Release reservation |
| AWAITING_PAYMENT | CANCELLED | Owner cancels (implemented); Host cancellation deferred | Release reservation |
| CONFIRMED | CANCELLED | Owner/host cancels under future policy | Release reservation; payment consequences handled separately |
| CONFIRMED | COMPLETED | System verifies checkout has passed | Historical stay; no future capacity |

DECLINED, CANCELLED, PAYMENT_FAILED, EXPIRED and COMPLETED are terminal in this initial
design. Retry means a newly validated request, not blindly resurrecting a failed
hold. EXPIRED is distinct from PAYMENT_FAILED so an unpaid timeout is not confused
with an attempted payment failure. Requests have no expiry state in this version.
All transitions not listed are invalid, including REQUESTED directly to CONFIRMED,
COMPLETED back to REQUESTED and late EXPIRED to CONFIRMED.

The service must validate actor/ownership and current state, use a database
transaction and reject stale/duplicate commands appropriately. A valid enum value
alone is not permission to perform a transition. Payment confirmation will require
verified, idempotent provider events in a later milestone; none exist now.

## Reservation semantics

REQUESTED consumes no capacity. AWAITING_PAYMENT reserves capacity immediately at
host acceptance, not after payment. CONFIRMED retains that same reservation. Count
the number of BookingPet rows for each reserving booking on each occupied night.
Dates use half-open `[start_date, end_date)` intervals. Two stays touching only at
checkout/check-in do not overlap. Summing every booking that overlaps any part of
an interval can overcount; calculate occupancy separately for every requested night.

`payment_expires_at` is required in AWAITING_PAYMENT. A duration is not hard-coded
in the schema; BOOKING_PAYMENT_WINDOW_SECONDS now defaults to 1800 (30 minutes). An
elapsed timestamp alone does not update a row: release should be recorded as an
explicit EXPIRED transition under the same reservation lock. Until then, treating
the hold as reserved is conservative. Milestone 7 acceptance does not expire stale
holds. Future expiry handling must use the same transaction protocol; no worker
exists yet.

Every failure/cancellation/expiry release and every capacity-affecting edit must
follow the same concurrency protocol. A completed stay occupies no future nights.
The booking service must prevent later edits to a reserved stay's pets/dates outside
this protocol. Snapshot prices are calculated server-side at request creation and
must not silently change at acceptance. The service fee is 10%, calculated in
integer cents with HALF-UP rounding at request creation. Acceptance preserves every
quote snapshot.

## Concurrency strategy

Implemented for pre-payment actions: serialize capacity mutations **per listing** using
a PostgreSQL row lock, within a short SQLAlchemy transaction at READ COMMITTED.

1. Begin a transaction. Lock the Listing row using SELECT FOR UPDATE. This stable
   parent row exists even when there are zero reservations; locking only matching
   bookings would leave an empty-set race.
2. Lock the target Booking next and re-read its state. Every competing path must
   lock listing first, then booking rows in a consistent UUID order if several are
   needed. Recheck host permissions, listing state, active owner/pets, species,
   ownership of every pet, nonempty pet selection, dates and the request snapshot.
3. Under that same listing lock, re-query current reserving bookings and
   their pet counts for the relevant nights. At READ COMMITTED this new statement
   sees changes committed by a preceding accepter after the lock wait.
4. Verify existing occupancy plus this request's pet count never exceeds the locked
   listing's capacity on any requested night. If it does, reject without reserving.
5. Set AWAITING_PAYMENT and payment_expires_at, update updated_at, then commit. The
   row lock is released only after the state/reservation is committed.

Two hosts/actions competing for the final place cannot both pass an old occupancy
check if **all** capacity writers follow this listing-lock convention. Capacity
reductions, accepted-stay date/pet edits, expiry, cancellations and payment outcomes
must use it too. A standalone CHECK constraint or the current B-tree index does not
solve this multi-row invariant. Direct SQL writers can still violate it; this is a
service protocol, not a database constraint or protection against direct SQL.

Confirmation and expiry must contend on the same listing/booking locks. After the
deadline or an EXPIRED transition, a late payment event cannot blindly confirm an
unreserved booking. Provider reconciliation/refund/compensation policy belongs to
the later payments milestone. Do not hold database locks while calling Stripe,
sending email or performing other external network work.

On lock timeout/deadlock/serialization failure, Milestone 7 rolls back and returns
409 booking_busy; there is no automatic replay. Reload before a deliberate retry
and never reuse stale occupancy. PostgreSQL tests demonstrate the last-capacity
race with independent connections; confirmation-versus-expiry is a future test.
Row locking is intentionally coarse per listing and may limit throughput for a hot
listing; measure before introducing per-night inventory rows or finer-grained locks.
No Redis, distributed lock or additional infrastructure is proposed.

Reference: [PostgreSQL 18 explicit locking](https://www.postgresql.org/docs/18/explicit-locking.html).

## Public advisory reads (Milestone 6)

Public search now calculates per-night occupancy using a SQL event sweep, counting
only AWAITING_PAYMENT and CONFIRMED. It neither changes state nor reserves capacity
and takes no row locks. Payment holds remain reserved until explicitly transitioned,
even after their deadline. Milestone 7 implements acceptance using the concurrency
strategy above; public reads remain advisory. See
[public discovery](listing-discovery.md) and ADR 0005.

## Milestone 7 scope boundary

Only new → REQUESTED, REQUESTED → DECLINED/AWAITING_PAYMENT/CANCELLED and
AWAITING_PAYMENT → CANCELLED are implemented. Repeat CANCELLED cancellation is
unchanged success; repeated accept/decline is a conflict. All actions lock Listing
then Booking, including non-reserving declines/cancellations for a uniform order.
Capacity configuration cannot be reduced below existing reserved peak occupancy.
No automatic expiry, payment success/failure, confirmed cancellation or completion
is implemented. See [ADR 0006](adr/0006-listing-locks-and-booking-quotes.md).

# Booking state machine (design only)

These are intended legal transitions for later services. This milestone stores
states but implements **no** booking endpoints, acceptance logic, capacity service,
pricing service, scheduled expiry or payment integration. PostgreSQL validates enum
membership and the basic row constraints, not old-to-new transitions.

| Current | Next | Responsible actor / condition | Capacity effect |
|---|---|---|---|
| REQUESTED | DECLINED | Listing host declines the request | None reserved |
| REQUESTED | CANCELLED | Owner withdraws request | None reserved |
| REQUESTED | AWAITING_PAYMENT | Host accepts after all transactional checks | Reserve all pets for each stay night |
| AWAITING_PAYMENT | CONFIRMED | Future payment service validates successful payment before deadline | Retain reservation |
| AWAITING_PAYMENT | PAYMENT_FAILED | Future payment service records definitive payment failure | Release reservation |
| AWAITING_PAYMENT | EXPIRED | System observes payment deadline elapsed | Release reservation |
| AWAITING_PAYMENT | CANCELLED | Owner/host cancels under future policy | Release reservation |
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
in the schema; the future service must select a bounded payment-window policy. An
elapsed timestamp alone does not update a row: release should be recorded as an
explicit EXPIRED transition under the same reservation lock. Until then, treating
the hold as reserved is conservative. Acceptance may expire stale holds within its
transaction, and a future worker can perform the same operation. Neither exists yet.

Every failure/cancellation/expiry release and every capacity-affecting edit must
follow the same concurrency protocol. A completed stay occupies no future nights.
The booking service must prevent later edits to a reserved stay's pets/dates outside
this protocol. Snapshot prices are calculated server-side at request creation and
must not silently change at acceptance. The service fee is 10%; cent-rounding and
pricing validation will be specified before implementing that service.

## Concurrency strategy

Proposed proportionate strategy: serialize capacity mutations **per listing** using
a PostgreSQL row lock, within a short SQLAlchemy transaction at READ COMMITTED.

1. Begin a transaction. Lock the Listing row using SELECT FOR UPDATE. This stable
   parent row exists even when there are zero reservations; locking only matching
   bookings would leave an empty-set race.
2. Lock the target Booking next and re-read its state. Every competing path must
   lock listing first, then booking rows in a consistent UUID order if several are
   needed. Recheck host permissions, listing state, active owner/pets, species,
   ownership of every pet, nonempty pet selection, dates and the request snapshot.
3. Under that same listing lock, process expired payment holds if necessary, locking
   affected booking rows in the same order. Re-query current reserving bookings and
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
future service protocol, not a guarantee already delivered by this migration.

Confirmation and expiry must contend on the same listing/booking locks. After the
deadline or an EXPIRED transition, a late payment event cannot blindly confirm an
unreserved booking. Provider reconciliation/refund/compensation policy belongs to
the later payments milestone. Do not hold database locks while calling Stripe,
sending email or performing other external network work.

On deadlock/serialization failure, roll back and use a bounded retry policy that
rechecks all rules; never reuse a stale occupancy result. Later PostgreSQL concurrency
tests must demonstrate the last-capacity race and confirmation-versus-expiry race.
Row locking is intentionally coarse per listing and may limit throughput for a hot
listing; measure before introducing per-night inventory rows or finer-grained locks.
No Redis, distributed lock or additional infrastructure is proposed.

Reference: [PostgreSQL 18 explicit locking](https://www.postgresql.org/docs/18/explicit-locking.html).

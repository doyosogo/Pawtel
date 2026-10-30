# Public Listing discovery and advisory availability

Milestone 6 implements public GET endpoints, not booking creation or acceptance.
No authentication, cookie, request-marker header or CSRF token is required. Existing
private Host/Pet authentication and write protections are unchanged.

## Endpoints and public boundary

- GET `/api/v1/listings`: paginated discovery.
- GET `/api/v1/listings/{listing_id}`: published detail.
- GET `/api/v1/listings/{listing_id}/availability`: published capacity snapshot.

Only PUBLISHED records qualify, including direct UUID access. Draft, archived and
missing records all return 404 listing_not_found. Malformed UUIDs, unknown query
parameters and invalid filters return the existing safe 422 validation_error envelope.
Public schemas expose ID, title, description, suburb/state/postcode/country, base and
additional-pet prices, configured capacity, sorted species and Host display_name/bio.
They omit Host/User IDs, email, timestamps, lifecycle/private management metadata and
all authentication state. Only display_name and identity are loaded from User; secret
columns are not selected. Host bio is deliberately public marketplace text. Responses
retain current no-store policy; no new public cache invalidation scheme is introduced.

## Filters and pagination

Optional filters: state (existing uppercase Australian enum), suburb (trimmed,
case-insensitive exact textual match), postcode (four ASCII digits), repeated species
parameters, min_price_cents, max_price_cents, pet_count, check_in and check_out.
For example `?species=DOG&species=CAT&state=SA&limit=20` requires both species.
Separate EXISTS predicates implement ALL-species matching without multiplying results.
Duplicates and unsupported species are rejected. Suburb filtering is not substring,
fuzzy, radius or geographically validated matching; leading-zero postcodes survive.

Price bounds are nonnegative integer cents, minimum no greater than maximum, bounded
to JavaScript-safe integers consistently with Host configuration. They filter base
nightly price only: no additional-pet charge or 10% service fee is included. A future
server-side booking quote owns authoritative calculations.

pet_count is a positive integer (maximum PostgreSQL INTEGER). Alone it filters
configured maximum capacity; it does not invoke date availability. When either date
is supplied, both dates AND pet_count are mandatory. Checkout must follow check-in.
The focused availability endpoint requires all three values. A request exceeding
configured capacity returns available=false there and no matching search result.
No past-date or maximum-stay business policy is invented in this read-only milestone.

Pagination uses limit (default 20, 1–50) and offset (default 0, nonnegative, bounded
to PostgreSQL INTEGER). Response: items, limit, offset, has_more, next_offset. One
extra parent record determines has_more without a total COUNT. next_offset is null
at the end. Ordering is created_at descending, UUID descending; there is no published
timestamp in the schema. This is discovery order, not recommendations. Inserts and
lifecycle changes between offset pages can shift results; this is not snapshot/cursor
pagination. Deep offsets and total-count product requirements should be revisited
with realistic usage.

## Capacity algorithm

Stay dates represent half-open `[check_in, check_out)` local calendar intervals:
10–12 November occupies the 10th and 11th; the 12th is checkout, not an occupied night.
Only AWAITING_PAYMENT and CONFIRMED reserve capacity. REQUESTED, DECLINED,
PAYMENT_FAILED, CANCELLED, EXPIRED and COMPLETED do not. Elapsed payment deadlines
alone do not release holds: the future state-transition service must explicitly
expire them under its capacity transaction protocol.

SQL counts BookingPet rows per overlapping reserving Booking. Intervals are clipped
to the requested stay. Each contributes a positive pet-count event at its clipped
start and a negative event at its clipped end. Same-date changes are grouped BEFORE
a cumulative window sum per Listing. The maximum cumulative sum is peak nightly
occupancy because occupancy is constant between event dates. Empty bookings contribute
zero; future booking services must require at least one pet.

This event sweep is equivalent to checking each night, without generating a row per
calendar day. It handles long intervals without proportional date expansion. Two
adjacent two-pet stays in a capacity-three Listing leave one space throughout a
larger request; summing all overlapping bookings would incorrectly count four.

Remaining capacity is configured capacity minus peak reserved occupancy. Availability
requires remaining >= requested count. The response exposes listing_id, requested
check_in/check_out/pet_count, available and remaining_capacity_at_tightest_point.
Remaining means BEFORE adding this request and is clamped at zero if inconsistent
existing reservations exceed configured capacity. It reveals no owners, pets, booking
IDs, reservation dates or payment details. Aggregate capacity still inherently reveals
some occupancy information; it is intentional product information, not full anonymity.

## Advisory only, transactions and queries

**Search/availability does not reserve capacity or guarantee later acceptance.**
Reads use a single SQL statement snapshot and no row locks. Future Host acceptance
must recheck current capacity inside the listing-locked PostgreSQL transaction in
[booking-state-machine.md](booking-state-machine.md). AWAITING_PAYMENT reserves at
acceptance so competing accepted requests cannot reuse unpaid held capacity.

Collection/details eagerly join accepted species and the safe Host summary, avoiding
per-result queries. SQLAlchemy wraps the parent limit/offset before collection eager
joins; unique parent results are materialized deliberately. Availability aggregation
is joined to the filtered Listing query; the focused endpoint returns only aggregate
capacity. Tests capture a dated collection executing one SELECT/WITH statement and
inspect compiled SQL for event aggregation, window partitioning and absence of locks.

Existing ix_bookings_listing_status_dates supports listing/status/date lookup, and
BookingPet's composite PK starts with booking_id. The batched aggregate currently
considers overlapping reserving bookings across Listings before the final discovery
filter; PostgreSQL may choose scans at demo scale. No EXPLAIN benchmark, realistic
load measurement or speed claim is made. No new index/migration is justified yet.
Revisit predicate pushdown/candidate restriction, query plans, public status/sort and
location indexes with representative synthetic data; deep offsets and broad date
queries may become expensive. No generic query framework was added.

## Tests and deferred work

Protected PostgreSQL tests cover visibility/privacy, all-species filtering, text and
price filters, pagination/tied ordering, invalid combinations, all booking states,
adjacency, overlapping multi-pet occupancy, clipped stays, oversized requests,
read-only behavior and bounded query count. Booking rows are explicit test fixtures;
there is no temporary or production booking-creation endpoint.

Deferred: booking requests/acceptance, authoritative concurrency, ranking, geocoding,
images, public frontend, payments, messaging/reviews/notifications/admin. Existing
production rate-limiting and operational-hardening limitations still apply.

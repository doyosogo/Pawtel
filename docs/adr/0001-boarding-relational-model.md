# ADR 0001: Boarding MVP relational persistence

Status: accepted for Milestone 2 (2026-10-26).

## Context

PAWTEL needs an interview-explainable relational foundation for an Australian
boarding marketplace. One account can both own pets and host listings. Future
booking/payment services need durable relationships and historical prices, but
those workflows are not part of this milestone.

## Decision

Use PostgreSQL 18, SQLAlchemy typed models, UUID entity keys, timezone-aware
timestamps and explicit Alembic migrations. Keep User, an optional shared-primary-key
HostProfile, Pet, Listing, ListingAcceptedSpecies, Booking and BookingPet. Associations
use composite keys rather than redundant surrogate IDs. All listings are boarding;
there is no generic service/product hierarchy yet.

Store canonical lowercase/trimmed user email under a database normalisation check
and unique constraint. Keep authentication credentials/tokens out of this schema
until their lifecycle is designed. Store AUD prices/snapshots in integer cents.
Use native enums with explicit migration-owned creation/removal. Restrict parent
record deletion; cascade only dependent association rows.

Persist booking amounts and a payment deadline, including EXPIRED as a distinct
unpaid-hold outcome. Specify legal transitions and a per-listing row-lock protocol
for later services; do not pretend the schema already enforces capacity/permissions.
Use real migration-backed PostgreSQL integration tests in a protected separate
database, with transactional rollback and guarded migration round trips.

## Alternatives considered

- A separate host account or is_host Boolean: duplicates identity or cannot itself
  own host profile data; shared PK gives one optional profile without another login.
- accepts_dogs/accepts_cats columns: simple today, but a tiny species association is
  clearer and avoids changing listing columns for each species.
- JSON pet arrays or a single booking pet FK: weaken relational integrity or prevent
  multi-pet bookings. BookingPet directly represents the many-to-many relationship.
- Floating money or always reading listing prices: rounding ambiguity or rewritten
  historical amounts. Cents and required snapshots preserve the agreed quote.
- CITEXT or a functional email index: valid alternatives, but canonical storage plus
  ordinary uniqueness avoids an extension and rejects bypassing writers explicitly.
- Text enums with checks: easier vocabulary changes, but native enums give explicit
  shared database types and make their evolution a deliberate migration.
- Ownership triggers/composite duplicate owner FKs: more schema coupling than needed;
  validate BookingPet ownership in the later transaction instead.
- Exclusion constraint on listing/date: would prohibit all overlap, while PAWTEL
  allows overlap up to pet capacity. Parent-row locking is a simpler proposed fit.

## Consequences and trade-offs

PostgreSQL rejects invalid local facts even when Python is bypassed. It does not
calculate prices, reserve capacity, verify email or authorise actors. Required price
snapshots mean future request creation must supply a complete server-calculated
quote. Native enum removal/reordering needs care; updated_at is ORM-managed on
updates, not a trigger-backed audit log. Archived records retain references, so
privacy/retention policies need later design. Query-driven indexes are starting
choices, not measured performance claims. Coarse listing locks favour correctness
and simplicity over maximum write concurrency.

See [database design](../database.md) and [booking state machine](../booking-state-machine.md).

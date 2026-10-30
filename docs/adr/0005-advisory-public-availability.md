# ADR 0005: Advisory public capacity snapshots

Status: accepted for Milestone 6.

## Context

Public discovery needs date-aware capacity without implementing bookings. A read
cannot guarantee inventory remains available after its database snapshot.

## Decision

Expose only PUBLISHED Listings through explicit public schemas. Use half-open stay
intervals and count BookingPet rows only for AWAITING_PAYMENT/CONFIRMED. Compute peak
nightly occupancy using clipped booking-boundary events and a cumulative SQL window
sum. Group same-day arrivals/departures first. Public reads neither reserve nor lock.
Future Host acceptance must recheck under the shared listing-row transaction protocol.

## Alternatives and consequences

Summing every overlapping stay overcounts sequential reservations. Generated daily
rows are understandable but expand with date-range length; boundary events avoid
that expansion. Search locks would block writers without reserving anything after
response delivery. Advisory results can become stale immediately and aggregate
remaining capacity inherently reveals limited occupancy information. No performance
claim is made before representative data/query-plan measurements. Booking transitions
and concurrency enforcement remain deferred, not delivered by this read model.

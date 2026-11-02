# ADR 0006: Listing-row coordination and server-owned Booking quotes

Status: accepted for Milestone 7.

## Problem

Two acceptors can both observe the final capacity from advisory search. Multiple
Booking/Pet rows and empty reservation sets cannot be protected by a simple CHECK.
Owners also need a stable quote despite later Host price edits.

## Decision

Application/test engines explicitly select READ COMMITTED. Capacity-changing actions
lock Listing then Booking, re-read state
and per-night occupancy, transition and commit in one short transaction. Acceptance
reserves at AWAITING_PAYMENT; Owner cancellation releases under the same protocol.
Listing capacity edits use the existing parent write lock and reject reductions
below reserved occupancy. Public reads stay advisory and lock-free. Future payment
transitions must use this coordination point and keep provider calls outside locks.

Quotes are calculated on the server in integer cents at request creation, including
10% fee rounded HALF-UP. Persisted snapshots are not recalculated at acceptance.
No new schema was required. Committed migration history remains unchanged.

## Alternatives and trade-offs

A SELECT without a coordinating lock permits write skew. Locking only existing
reservations fails when the set is empty. Per-night inventory/version retries could
work but add schema/protocol complexity. Redis adds another authority without a need.
The Listing row is already shared by all reservations in this PostgreSQL application.

Coarse locking serializes a hot Listing, so measure contention before redesigning.
Waits are bounded and return a safe conflict; clients reload before retrying. Direct
SQL can bypass service rules. Explicit future requoting may be needed for old requests;
implicit price changes would undermine the submitted quote. Request creation remains
non-idempotent. Payment/webhook idempotency and automatic expiry are still deferred.

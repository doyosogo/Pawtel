# ADR 0004: Verified, private Host management on one account

Status: accepted for Milestone 5.

## Context

The existing schema separates optional hosting from User identity. Listings need
private management before public browsing or booking workflows exist.

## Decision

Reuse HostProfile's shared User key and current Listing/species tables without a
migration. Require the existing active, verified-user dependency for all Host APIs.
Derive ownership from authentication and scope resource queries by ID and Host key.
Foreign/missing private resources share 404. Keep drafts preparable without species;
publication requires at least one. Archive preserves rows and is terminal through
this API. Listing/species writes share one service-owned transaction.

## Alternatives

Separate host accounts/roles duplicate identity. Client-supplied ownership is unsafe.
Global lookup followed by permission checks is easier to misuse. PostgreSQL RLS
would add caller-context plumbing to an application-owned access model. Hard delete
would undermine future historical references. New schema abstractions are unnecessary.

## Consequences

One person can own pets and host. Verification gates marketplace configuration while
private Pet preparation stays available before verification. These contextual rules
remain service responsibilities, not FK guarantees. PUBLISHED does not yet expose a
public marketplace. Archives have no restore operation, and concurrent edits are
last-successful-writer-wins; neither bookings nor optimistic locking is implemented.
See the Host/Listing API contract for validation, transaction details and limitations.

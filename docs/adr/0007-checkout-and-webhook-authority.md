# ADR 0007: Checkout Sessions and webhook-authoritative payment state

Status: accepted for sandbox-only Milestone 8.

## Context

PAWTEL already reserves capacity at acceptance. Stripe and PostgreSQL cannot share
one atomic transaction; callbacks can be duplicated, reordered or beat API responses.

## Decision

Use official SDK Checkout Sessions (elements/payment/AUD/card-only) rather than raw
PaymentIntent orchestration. Persist attempt identity and fixed request snapshots;
reuse deterministic provider idempotency keys. Make external calls between short DB
transactions, never under inventory locks. Only signed raw-body success webhooks
with matching provider identity, amounts/currency and eligible Booking can confirm.
Persist unique Event IDs in the same transaction as Booking/attempt mutations.

Keep Listing-first/Booking-second/attempt-third locking and explicit READ COMMITTED.
Refresh ORM rows after external calls. Browser redirects are navigation, not payment
proof. Public availability stays advisory. One bounded Checkout deadline aligns the
hold with Stripe expiry. Cancellation commits locally then expires provider sessions;
late paid/terminal mismatches remain visible as reconciliation, never resurrect stays.

## Alternatives and consequences

Raw PaymentIntents require more payment-lifecycle orchestration. Holding DB locks
across provider calls harms availability and does not create distributed atomicity.
In-memory deduplication fails across restarts/processes; unique Event IDs survive.
Queues/microservices add infrastructure without a measured need for these short SQL
webhooks. Coarse locks serialize hot Listings; timeouts, recovery and operational
reconciliation remain explicit. Manual refunds, payout/Connect flows and production
hardening are deferred. A partial unique index prevents concurrent unresolved local
attempts; history retains failed/expired attempts without storing client secrets.

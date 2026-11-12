# PAWTEL product scope

PAWTEL is an Australian pet-boarding marketplace portfolio MVP for dog/cat Owners
and Hosts. Boarding is the current service scope; synthetic accommodation is not
a real service offering. [Architecture](architecture.md) describes implementation;
ADRs retain the historical decisions rather than implying every model is a feature.

## Implemented journey

- Public published-Listing discovery/detail, suburb/location/species/date/Pet-count
  filters and advisory availability. No fabricated distance, review or amenity data.
- Email/password registration and opaque sessions, CSRF, active/verified account
  rules and private owner-managed Pet Profiles. Real email delivery is absent.
- Optional HostProfile on the same User; Listing draft/publish/archive, pricing,
  capacity, accepted species, structured Australian location and Cloudinary media.
- Verified Owner Booking requests with selected owned Pets and server-owned integer
  AUD price snapshots, including the 10% PAWTEL service fee.
- Host accept/decline and allowed Owner cancellation. Acceptance rechecks capacity
  under Listing-first PostgreSQL locks; public availability does not reserve space.
- Stripe sandbox Checkout Elements, durable attempts, signed/deduplicated webhook
  confirmation, expiry/recovery and late-payment reconciliation. No live charges.
- Frontend Owner/Host workflows, synthetic seed tooling, provider fakes, PostgreSQL
  integration/concurrency tests, real headless E2E and verified GitHub CI.
- Safe diagnostics, production configuration validation and a prepared same-origin
  deployment path. No hosted release or public URL is currently verified.

Australian states/postcodes and AUD are explicit assumptions. Textual location is
not geocoding or validated suburb/postcode pairing. Passwordless fictional browse
seeds and login-enabled workflow identities have different purposes; see the
[local workflow](../README.md#try-the-full-workflow-locally).

## Deliberately outside this MVP

Reviews, messaging, notifications, admin, maps/geocoding, daycare, house sitting,
drop-ins and dog walking. No Host payouts/Stripe Connect, saved cards, subscriptions
or automatic refund product flow. Do not advertise these as implemented features.

## Before real customers

Manual provider provisioning and deployment verification; real email/recovery;
privacy/legal/support/retention processes; scheduled maintenance/reconciliation;
shared abuse controls; restore drills, security/load assessment and final CSP review.
The portfolio deployment intentionally disables public registration and uses private
synthetic demo access. Normal local registration remains functional, with verification
requirements unchanged. This is production-shaped, not production-ready.

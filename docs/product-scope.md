# PAWTEL product scope

PAWTEL is an Australia-wide pet boarding marketplace for owners and hosts. Adelaide can be heavily represented in future synthetic demo data.

## MVP product decisions (planned)

- Pet boarding only, supporting dogs and cats.
- One user account type; existing users can enable Host mode.
- Owners create pet profiles; hosts create accommodation listings.
- Owners select a listing, dates and pets and send a booking request. Hosts review owner and pet information, then accept or decline. Accepted requests proceed through payment and confirmation.
- Hosts configure base nightly prices and additional-pet fees. PAWTEL charges a 10% service fee; calculation details will be designed later.
- Stripe TEST mode for the MVP payment integration.
- Two-sided reviews only after completed stays.
- Required email verification.
- Realistic demo/seed hosts, users, pets, and listings.

## Future expansion

The architecture should accommodate daycare, house sitting, drop-in visits, and dog walking. These services are outside the boarding MVP.

## Explicitly deferred functionality

Milestone 2 added PostgreSQL/domain persistence. Milestone 3 adds password registration,
opaque sessions, login/logout/self, CSRF and email-verification persistence/consumption.
External email delivery, public resend, password reset, OAuth, the polished auth UI,
payment workflows, automatic expiry/completion, confirmed cancellations/refunds,
messaging, dashboards, ranked/geospatial search, maps, reviews and seed data remain deferred. Existing
domain models do not imply working marketplace features. No admin feature exists.

Milestone 4 implements private owner-managed Pet Profile APIs (create/list/get/PATCH/
soft archive), including pre-verification setup for active users. No Pet frontend,
medical/vaccination/image data, restore feature or host-review access was added.

Milestone 5 adds optional HostProfile enablement/bio management and private Listing
configuration, including accepted species and draft/published/archive lifecycle.
Verified email gates all Host management. At that milestone public browsing and
availability were deferred; Milestone 6 below adds them as read-only APIs. Host UI,
images and geocoding remain deferred.

Milestone 6 implements public PUBLISHED discovery/detail, textual filters, pagination
and advisory per-night capacity. Public browsing is now available as an API only;
ranking, geocoding, images and the search frontend remain deferred. That milestone
did not implement booking creation/acceptance; Milestone 7 below adds them.

Milestone 7 implements verified Owner requests with server-priced snapshots, private
Owner/Host review, Host accept/decline and Owner pre-payment cancellation. Acceptance
rechecks capacity under PostgreSQL Listing-row locking and ends at AWAITING_PAYMENT.
Payments, expiry, confirmed cancellations/refunds, completion and booking UI remain
deferred. Public availability remains advisory, not a reservation.

Milestone 8 adds sandbox-only Checkout Sessions, durable payment attempts/webhook
receipts, signed success confirmation, expiry/recovery and cancellation reconciliation.
No live charges, Connect/Host payouts, transfers, saved cards, subscriptions, automatic
refunds or checkout UI. Individual declined cards do not terminally fail open Checkout.
Real sandbox credentials/verification are separate from deterministic offline tests.

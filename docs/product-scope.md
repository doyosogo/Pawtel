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
booking workflows, authoritative quote calculation, payments,
messaging, dashboards, search, maps, reviews and seed data remain deferred. Existing
domain models do not imply working marketplace features. No admin feature exists.

Milestone 4 implements private owner-managed Pet Profile APIs (create/list/get/PATCH/
soft archive), including pre-verification setup for active users. No Pet frontend,
medical/vaccination/image data, restore feature or host-review access was added.

Milestone 5 adds optional HostProfile enablement/bio management and private Listing
configuration, including accepted species and draft/published/archive lifecycle.
Verified email gates all Host management. Public marketplace browsing, Host UI,
images, geocoding and availability remain deferred. PUBLISHED is stored lifecycle
state, not evidence of a working public marketplace.

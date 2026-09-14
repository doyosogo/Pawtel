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

The current milestone is foundation only. Authentication, email verification, Host mode, listings, pets, booking workflows, pricing, payments, messaging, dashboards, search, maps, reviews, and seed data are not implemented. Domain models and database migrations will be designed in a later milestone. External integrations are also deferred. An admin panel is also outside this foundation milestone.

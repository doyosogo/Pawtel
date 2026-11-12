# Architecture decision index

These concise records explain concrete trade-offs in the implemented system.
Earlier milestone wording records the decision at that time; the current
[architecture overview](../architecture.md) describes the completed boundaries.

| ADR | Decision |
| --- | --- |
| [0001](0001-boarding-relational-model.md) | Relational boarding model and constraints |
| [0002](0002-opaque-session-authentication.md) | Opaque session cookies, hashed credentials and CSRF |
| [0003](0003-private-pet-ownership.md) | Owner-derived private Pet resources and soft archive |
| [0004](0004-verified-private-host-management.md) | Optional Host identity and verified Listing management |
| [0005](0005-advisory-public-availability.md) | Public published-only discovery and advisory capacity |
| [0006](0006-listing-locks-and-booking-quotes.md) | Listing-first locking, authoritative quote snapshots |
| [0007](0007-checkout-and-webhook-authority.md) | Checkout attempts, idempotency and webhook authority |
| [0008](0008-cloudinary-listing-media.md) | Server-mediated Cloudinary media and relational metadata |

Operational choices (edge rate limits, explicit migrations, safe JSON diagnostics,
isolated headless E2E) are documented together in the [runbook](../operations.md),
without adding an ADR solely to increase the count.

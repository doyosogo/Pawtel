# Résumé material

Choose a few bullets that match the role; do not use every variation together.
These describe Victor's portfolio implementation, not customer adoption, revenue,
production scale or measured performance improvements.

## Three concise options

- Built PAWTEL, an Australian pet-boarding portfolio MVP using React/TypeScript,
  FastAPI and PostgreSQL, spanning discovery, Owner/Host workflows and test payments.
- Implemented concurrency-safe Booking acceptance and server-owned AUD price
  snapshots, with ownership-scoped resources and cookie/CSRF authentication.
- Integrated Stripe Checkout/webhook confirmation and Cloudinary Listing media,
  with deterministic provider-failure tests and PostgreSQL-backed GitHub CI.

## Three technical alternatives

- Serialized competing Booking reservations with PostgreSQL Listing-first row locks
  and transactional capacity rechecks; verified final-space races using separate connections.
- Persisted Stripe payment attempts and deduplicated signed webhook events; handled
  late payments after cancellation and cloud-media/database partial failures through
  explicit reconciliation and cleanup states.
- Validated 520 backend, 141 frontend and 3 real React/FastAPI/PostgreSQL E2E tests
  locally, alongside a verified GitHub-hosted Linux CI baseline and isolated test data.

## Project description

PAWTEL is a production-shaped boarding marketplace portfolio MVP built with
React/TypeScript, FastAPI and PostgreSQL. It demonstrates secure Owner/Host workflows,
transactional reservation/pricing, Stripe sandbox payments, Cloudinary media and
verified CI; public deployment remains a manual handoff, not a claimed live service.

[Remote baseline evidence](https://github.com/doyosogo/Pawtel/actions/runs/43317246922).
Update any numbers you choose to copy if later suites change. Do not relabel the
project as production-ready or claim live users without evidence.

# PAWTEL documentation

Start with the [repository overview and local demo](../README.md). PAWTEL currently
implements boarding for dogs/cats in Australia; it is a portfolio MVP, not a live
production marketplace.

## For recruiters and interviews

- [Frontend showcase](frontend-showcase.md): verified live synthetic demo, hosted checks, persona exploration and manual Vercel setup.

- [Portfolio case study](portfolio-case-study.md): problem, decisions, trade-offs and evidence.
- [Résumé bullets](resume-bullets.md): concise and technical options without invented business metrics.
- [Interview guide](interview-guide.md): spoken explanations and technical STAR stories.
- [Manual screenshot plan](images/README.md): states to capture yourself; no fake images.

## System and domain contracts

- [Architecture](architecture.md): current boundaries, transaction flow, failures and deployment diagram.
- [Authentication](authentication.md), [security interview detail](authentication-interview.md).
- [Database/setup/ERD](database.md), [private Pet Profiles](pet-profiles.md).
- [Host/Listings/media](host-listings.md), [public discovery](listing-discovery.md).
- [Bookings](bookings.md), [state machine](booking-state-machine.md).
- [Payments](payments.md), [payment interview detail](payments-interview.md).
- [ADR index](adr/README.md): all eight decisions retained, including their historical context.
- [Product scope](product-scope.md), [engineering principles](engineering-principles.md).

## Run, verify and release

- [Operations](operations.md): test commands, isolated E2E, CI and diagnostics.
- [Deployment guide](deployment.md): selected provider path, pricing references, secrets and rollback.
- [Environment inventory](deployment-environment.md): required, conditional and local-only values.
- [Numbered deployment preflight](deployment-preflight.md): exact manual phases, costs and cleanup.
- [Final deployment checklist](deployment-checklist.md): concise manual handoff, no automatic provisioning.

The README is the primary location for current test counts. The verified remote
baseline is [run 43354658127](https://github.com/doyosogo/Pawtel/actions/runs/43354658127)
for `674f482`; this is CI evidence, not proof of a public deployment.

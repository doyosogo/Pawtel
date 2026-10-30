# Engineering principles

PAWTEL aims to demonstrate maintainable software through complete end-to-end workflows. These principles guide later milestones; they do not prescribe every implementation in advance.

- Enforce business rules, ownership and permissions on the backend.
- Model booking states explicitly and permit only legal state transitions.
- Preserve relational integrity with deliberate database constraints.
- Use database transactions and concurrency-safe capacity handling.
- Calculate prices on the server, including nightly rates, additional pets and the 10% service fee.
- Process payments securely; authenticate webhooks and handle deliveries idempotently.
- Prefer meaningful integration tests and a small number of valuable end-to-end tests.
- Use realistic synthetic demo data without exposing personal information.
- Make local development reproducible with documented commands and dependency locks.
- Keep responsibilities clear, files reasonably small and architecture proportional to a finishable project.
- Document limitations honestly, including planned capabilities that are not implemented.

Milestone 2 implements relational persistence and records a proposed booking/concurrency
design. Milestone 3 implements authentication and verification persistence/services.
Booking services, real email delivery and payment processing remain future work.
Database constraints alone do not claim to implement those workflows.

Milestone 4 applies backend ownership enforcement to private Pet Profiles through
owner-scoped SQL reads and writes, safe response schemas and cross-user integration
tests. A valid foreign key is not proof that the HTTP caller owns the referenced row.

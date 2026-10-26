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

Milestone 2 implements relational persistence and records a proposed booking/concurrency design. Authentication, booking services and payment processing remain future milestones. Database constraints alone do not claim to implement those workflows.

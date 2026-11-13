# Manual deployment procedure and acceptance gate

**No public URL has been verified.** This is a handoff for you, not an automatic
provisioner. Start with the [environment inventory](deployment-environment.md) and
[architecture/operational guide](deployment.md). Provider accounts, resources,
secret values, charges and DNS are always your manual actions.

## Phase A — account, repository and cost approval

1. Review and push the approved milestone yourself. Verify ALL three jobs green
   for the EXACT release SHA; a green older run is not sufficient. The inspected
   baseline is `da2255d` / [run 43317246922](https://github.com/doyosogo/Pawtel/actions/runs/43317246922).
2. Sign into Render yourself. Choose your own workspace/account; read its actual
   billing estimate before confirming paid resources. Connect the PAWTEL GitHub
   repository with permissions you review. Do not supply deploy write secrets to PR CI.
3. Use the root `render.yaml` Blueprint, or enter its same settings manually. Leave
   Root Directory **blank**, not backend: the build needs both projects.
4. Choose **Singapore**, one `0.5c-512mb` web instance, Python runtime, one worker.
   Keep automatic deploy **Off**. A first Blueprint creation can still start its
   initial build; subsequent deploys remain intentional manual actions.
5. Do not enable PR previews, extra instances, disks, autoscaling or paid extras
   merely to complete this portfolio. They can create separate charges.

### Current cost checkpoint — reviewed 13 November 2026

The [official pricing page](https://render.com/pricing) lists Hobby workspace at
$0 plus compute, selected web compute at **US$7/month**, selected PostgreSQL compute
at **US$6/month**, and 1GB database SSD included. The configured 1GB baseline is
therefore **US$13/month before tax and metered extras**. Additional database storage
is advertised at **US$0.30/GB-month**. Check the actual creation quote: usage,
bandwidth/build allowances, paid workspace upgrades, added storage and taxes can
change the bill. No AUD conversion or guaranteed monthly invoice is asserted.

The [free tier](https://render.com/docs/free) can preview the product, but web
services sleep after idle time and free PostgreSQL expires after 30 days with no
backups. It is not a stable recruiter link. Cloudinary's free allowance may cover
synthetic media if you stay within its quota; Stripe remains test-only. Do not
provision until you accept the shown estimate. Nothing has been purchased here.

## Phase B — managed PostgreSQL

6. Create **PostgreSQL 18**, Singapore, compute `0.1c-256mb`, **1GB**, database AND
   user `pawtel_portfolio`. Never bind an existing real-user database.
7. Keep external access disabled (`ipAllowList: []`); same-region internal access
   remains available. Do not add `0.0.0.0/0` to make a local connection convenient.
8. Let Blueprint bind `DATABASE_URL` from this database's internal connection
   string. Do not copy it into source, chat, frontend variables or screenshots.
   SQLAlchemy normalizes the standard provider URL to Psycopg and requires TLS.
9. Review connection/backups assumptions: selected tier supports up to 100
   connections; application pool is two plus two overflow per process, with pre-ping,
   five-minute recycle and bounded waits. Readiness/migration connections are separate.
   The demo uses the DB owner for both migration/runtime; least-privilege role
   separation is a real-launch improvement, not a claimed implemented control.
10. Paid PostgreSQL on Hobby currently provides **three-day PITR**, Pro+ seven days;
    Free provides none. A recovery creates another DB to validate/repoint and may
    cost extra. No actual restore drill has occurred. [Policy](https://render.com/docs/postgresql-backups).

## Phase C — exact Web Service environment

11. Confirm Blueprint values: `PYTHON_VERSION=3.14.8`, `NODE_VERSION=24.13.1`,
    `APP_ENV=production`, `DEBUG=false`, `SESSION_COOKIE_SECURE=true`,
    `SERVE_FRONTEND=true`, `PORTFOLIO_DEMO=true`. Render supplies `PORT`.
12. Copy the ACTUAL assigned service hostname. Set `BACKEND_CORS_ORIGINS` to a JSON
    array containing its HTTPS origin, and `ALLOWED_HOSTS` to its hostname JSON array.
    No trailing slash, scheme in hosts, wildcards or localhost. If the hostname is
    unavailable until resource creation, configure it before the first successful
    release; initial missing configuration fails closed.
13. Omit `TEST_DATABASE_URL` and ALL E2E/runner values. Do not upload root `.env`.
    Keep Stripe/Cloudinary entirely omitted until ready for Phases F/G; a lone local
    Stripe return URL is not a valid production-disabled configuration.
14. Choose a private `PAWTEL_DEMO_PASSWORD` (15–128 characters) in the provider secret
    store for operator setup. It is not a public shared password or admin credential.
    Never add server/admin secrets under VITE_. See the complete [inventory](deployment-environment.md).

## Phase D — build, release migration and startup

15. Build Command: `bash deploy/render-build.sh`. It installs the pinned backend
    snapshot into Render's runtime and uses `npm ci --include=dev` so TypeScript/Vite
    are present even under `NODE_ENV=production`; they are build tools, not browser secrets.
16. Pre-Deploy Command:
    `cd backend && python -m tools.validate_deployment && python -m alembic upgrade head`.
    Inspect success before routing the release. This paid hook is the migration
    phase, not a command every app worker runs.
17. Start Command: `bash deploy/render-start.sh`. It uses `$PORT`, no reload, one
    worker, JSON logging, bounded concurrency, graceful SIGTERM and no blanket
    forwarded-header trust. Cookie security and public URLs are explicit settings.
18. Health Check Path: `/ready`. It tests DB/schema before traffic and can cause
    restarts during dependency failure; `/health` is process-only liveness once
    started. Startup itself requires schema readiness. Neither calls providers.
19. Trigger the reviewed release yourself. Inspect pre-deploy/startup logs, then
    check `/health`, `/ready`, homepage and a direct `/stays` refresh. FastAPI must
    still return JSON for `/api/v1/listings`; unknown `/api` paths must not serve SPA HTML.

## Phase E — guarded synthetic account setup

20. **After migrations and successful startup, before sharing login access**, open
    Render's shell yourself and run from repository root:

    ```sh
    cd backend
    PORTFOLIO_SEED_CONFIRM=pawtel_portfolio python -m app.scripts.seed_portfolio
    ```

21. It requires production + portfolio mode + dedicated exact TLS DB/role + actual
    non-superuser identity, and refuses unrelated User rows. It creates/reuses
    `workflow.owner@pawtel.example.com` and `workflow.host@pawtel.example.com`, normally
    hashed Argon2id passwords, verified synthetic identities, DOG/CAT Pets and a
    useful published Listing. It seeds **no Bookings** and prints no passwords.
22. Run it twice if you want operator idempotency confirmation. It preserves edited
    data/history; it is NOT a destructive reset. To rotate invited access, change
    the private password and rerun: old synthetic sessions are revoked. Never use
    the local `seed_workflow` command on the managed environment.
23. Share access privately only when needed, rotate afterward and use synthetic
    inputs. Public browsing is open, registration is server-disabled, no verification
    email is promised, and there is no Admin role or auth bypass.

## Phase F — Stripe sandbox, performed by you

24. Sign into Stripe yourself and select the intended **sandbox/test environment**,
    not live mode. Find that environment's test secret and publishable keys.
25. In Workbench → Webhooks/Event destinations, create/select a destination for
    events from this account, with **snapshot** events and endpoint:
    `https://<actual-service-host>/api/v1/webhooks/stripe`.
26. Select only `checkout.session.completed` and `checkout.session.expired`. Align
    destination event API version with backend `2026-10-28.endive`; do not silently
    substitute a different payload contract. The existing SDK/session API stays pinned.
27. Copy THIS destination's signing secret privately into `STRIPE_WEBHOOK_SECRET`.
    It is different from a local Stripe CLI listener secret. Configure
    `STRIPE_SECRET_KEY`, `VITE_STRIPE_PUBLISHABLE_KEY`, and
    `STRIPE_RETURN_URL=https://<actual-service-host>/checkout/return` from the same
    sandbox. Do not configure the legacy backend `STRIPE_PUBLISHABLE_KEY`.
28. Rebuild/redeploy yourself: VITE_ is build-time, while backend keys/return URL are
    runtime. No CLI forwarding is needed for a reachable deployed HTTPS endpoint.
29. Create/accept a real synthetic Booking through the app, then use Pay securely.
    Enter Stripe's documented sandbox card data **only inside Stripe Elements**:
    [test cards and failure cases](https://docs.stripe.com/testing#cards). Use a future
    expiry and test CVC as instructed there. Never enter real card data, log it,
    commit it or include it in portfolio captures. Test a decline/retry too.
30. Inspect destination delivery success yourself and observe CONFIRMED from PAWTEL's
    backend. Browser return/polling only observes state. Late payment after cancellation
    is reconciliation, not resurrection. [Official webhook setup](https://docs.stripe.com/webhooks).

## Phase G — Cloudinary, performed by you

31. Select/create a dedicated demo product environment yourself. Set server-side
    `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` and redeploy.
    No VITE_ media credential and no unsigned public upload preset is required.
32. Login as invited Host, save a Listing draft, upload synthetic JPEG/PNG/WebP,
    reorder/remove if desired, publish and verify public card/gallery CDN delivery.
    Current limits remain six images, 5MiB each, dimensions 200–6000px and 24M pixels.
    Effective limit is the minimum of app/account/platform; manually test a near-limit
    file because real Render ingress/Cloudinary quotas were not exercised here.
33. Provider upload/delete failures keep durable cleanup responsibility; don't delete
    DB metadata blindly while leaving cloud assets. Use existing media maintenance
    with reviewed scope. No real upload was performed during this preflight.

## Phase H — public acceptance and recruiter release

34. Run the read-only operator smoke tool from backend (project environment active),
    replacing the placeholder with your real origin:

    ```sh
    python -m tools.deployment_smoke --frontend https://<actual-service-host>
    ```

    It requires HTTPS, performs bounded anonymous reads, follows no redirects and
    prints no response bodies/secrets. It does not login, book or upload. Only the
    explicitly local rehearsal may opt into loopback HTTP.

35. Personally check: homepage; search; Listing images/gallery; Owner login; Pets;
    request; Host inbox/login/accept; Owner AWAITING_PAYMENT/deadline/price; sandbox
    checkout; signed-webhook CONFIRMED; Host Listing editor/photo; logout/back;
    mobile width/keyboard; `/health`; `/ready`; demo banner/registration refusal.
36. Inspect HTML/API security headers for stripping/duplicates and cookie attributes
    on the actual HTTPS host. Use a response request UUID to find its safe JSON log
    in Render. Never enable body/cookie/provider debug logging for diagnosis.
37. Verify all checks before publishing the single README live-status location and
    GitHub website field. No live URL exists yet. Keep private invited credentials
    off GitHub and use your own manually reviewed screenshots only.

## Rollback rehearsal boundary

For code-only failure, manually choose the last known-good Render deployment/commit;
React/API roll back together, auto-deploy remains Off. This does not restore env
values, SQL writes, schema, payments or cloud assets. For migration trouble prefer
backward-compatible changes or a forward fix; exact-head startup checks mean an old
release may refuse the newer schema. Review before any downgrade. Validate a restored
DB separately and reconcile external state before repointing. No remote rollback or
paid recovery was performed here.

## Stop spending later — your manual actions only

1. Stop inviting traffic; leave auto-deploy Off and disable unwanted preview/Blueprint
   automation so deleted resources are not recreated by a later sync.
2. In Render service management/Settings choose Suspend for a temporary pause and
   verify its state/billing. To retire it, review backups/log needs and delete ONLY
   the dedicated demo web service yourself. Stopping compute does not erase DB costs.
3. PostgreSQL is a separate paid resource. Export/secure data you need, review
   recovery requirements, then delete the dedicated demo DB yourself if retiring.
   Deletion is destructive; do not assume PITR survives deletion. Review any recovery
   clones, previews, disks and paid workspace subscriptions separately in Billing.
   [Billing model](https://render.com/articles/how-paas-billing-works).
4. Render deletion does not clean Cloudinary. Stop uploads/revoke dedicated app
   access, review and remove only `pawtel/listings/...` demo assets you actually own,
   preserving unrelated assets. Review Cloudinary's plan/add-ons/billing yourself;
   deleting an app is not a paid-plan cancellation.
5. Disable the sandbox Stripe event destination when retiring it, and revoke only
   dedicated test keys if appropriate. Sandbox transactions move no real money and
   do not incur live payment-processing charges; this does not cancel other paid
   provider products you may have chosen. No live mode was enabled by PAWTEL.
6. Confirm provider resource lists and subsequent billing yourself. No suspension,
   deletion, cancellation or resource purchase was performed by this preflight.

## Local verification evidence and its limits

Milestone 16 used a tracked-files-only copy with no `.env`, `node_modules` or build
output, a fresh isolated Python venv, and a PATH exposing runtimes but no global
TypeScript/Vite. Under `NODE_ENV=production` the original install omitted build
packages and failed; explicit `npm ci --include=dev` fixed the clean build. Compiled
frontend/dist, local build binaries and dependency consistency were verified.

A fresh disposable loopback PostgreSQL18 cluster negotiated real TLS with a
non-superuser `pawtel_portfolio` database/role. Only that new database underwent
upgrade → downgrade base → upgrade and drift checks. The exact production start
script ran without reload under APP_ENV=production, serving health/readiness, SPA
deep routes and JSON API boundaries. Guarded seeding/idempotency/rotation, normal
Owner/Host session+CSRF requests, foreign-resource rejection, safe DB-error responses,
readiness failure/recovery, schema-mismatch startup refusal and graceful shutdown
were exercised. Logs were JSON and checked for generated private/canary values.
Temporary servers were stopped; development data was not used for this rehearsal.

Loopback HTTP with synthetic Host/Origin headers modeled the backend behind TLS
termination; Secure cookie attributes and authenticated headers were checked in
memory. This is not a public HTTPS/browser/proxy test. Demo banner/registration
presentation is covered by component tests plus the real public configuration
contract, not a claimed visual inspection. The smoke helper performed anonymous
reads locally; public HTTPS and actual provider settings still need Phase H.
No real Stripe/Cloudinary credentials, uploads, payments or dashboard actions were
used. Standard regression/migration tests separately use their existing guarded
test database. Current counts live in the README; no production-ready certification
is implied by these checks.

A refused production startup emits the safe `startup_not_ready` JSON event. Check database connectivity and migration/schema readiness; exception text and connection values are not logged.

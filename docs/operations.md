# Operations, CI and deployment

PAWTEL is a production-shaped portfolio MVP, not an audited production service.
No deployment occurs automatically. Native macOS development remains supported.

## Reproducible checks

Use Python 3.14, Node 24 and PostgreSQL 18. The backend runtime/dev snapshot is
`backend/requirements-dev.lock`; frontend installation uses `npm ci`. The backend
snapshot previously omitted Cloudinary/Pillow/six; those existing dependencies are
now included. There is no unrelated dependency upgrade.

```sh
cd backend
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -m pip check
python -m alembic current
python -m alembic check
cd ../frontend
npm ci
npm run lint
npm test -- --run
npm run build
npm run format:check
```

Integration tests retain their strict local `pawtel_test` database AND role guard,
PostgreSQL 18/non-superuser checks, and distinct development/test databases. Tests
exercise real Alembic DDL, including guarded downgrade/upgrade tests. Never point
these at developer/production data.

`.github/workflows/ci.yml` has backend quality/tests, frontend quality/tests/build,
and a dependent E2E job. Backend and E2E jobs each receive a disposable PostgreSQL
18.6 service. Bootstrap superuser credentials are synthetic CI-only strings;
application/test roles are non-superusers and own only their dedicated databases.
Migrations run explicitly before tests. pip/npm caching is keyed by dependency
files; browsers are installed from the pinned Playwright version. Dependencies
and browser downloads need network access; application tests do not need Stripe,
Cloudinary or email services. No provider/repository secrets are passed to jobs.

Workflow permissions are `contents: read`, checkout does not retain credentials,
and ordinary `pull_request` is used, never privileged `pull_request_target`.
The verified remote baseline is
[run 43317246922](https://github.com/doyosogo/Pawtel/actions/runs/43317246922)
for `main` commit `da2255d` (checked 13 November 2026): backend, frontend and E2E
all succeeded on GitHub-hosted Linux. Local checks alone would not prove that;
future commits need their own remote result. See the [CI incident story](portfolio-case-study.md#cie2e-and-deployment-hardening).
Action major versions and the Postgres patch are explicit; image/action digests
are not pinned. Review trusted upstream updates rather than silently auto-upgrade.

## Isolated headless E2E

The three Playwright scenarios cover (1) public load → Owner login/search/Pet/date
selection → real request → Host login/accept → Owner AWAITING_PAYMENT; (2) private
route redirect and real Pet creation; (3) Host draft hidden publicly, then visible
after publication. HTTP requests are NOT intercepted. React, Vite proxy, FastAPI,
cookie/CSRF handling and PostgreSQL are real. The suite stops before Stripe;
existing adapter and component tests cover external boundaries deterministically.

Create an additional local non-superuser login/database named exactly
`pawtel_e2e`, using the PostgreSQL 18 cluster described in [database setup](database.md).
From its peer-authenticated administrator psql session, first check whether these
already exist. Do not recreate existing roles or reset unrelated credentials:

```sql
CREATE ROLE pawtel_e2e LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password pawtel_e2e
CREATE DATABASE pawtel_e2e OWNER pawtel_e2e;
REVOKE ALL ON DATABASE pawtel_e2e FROM PUBLIC;
ALTER ROLE pawtel_e2e SET timezone='UTC';
```

Set `E2E_DATABASE_URL` privately to a psycopg URL using that role/database and the
local cluster port; URI-encode the password. Supply it through an ignored `.env`
entry or environment. The runner intentionally does not source arbitrary shell
`.env` files. To safely read a value already added to the root `.env`:

```sh
cd frontend
export E2E_DATABASE_URL="$(../backend/.venv/bin/python -c 'from dotenv import dotenv_values; print(dotenv_values("../.env").get("E2E_DATABASE_URL", ""))')"
PLAYWRIGHT_BROWSERS_PATH=../.cache/pw-browsers npm run e2e:install
npm run test:e2e
unset E2E_DATABASE_URL
```

The runner refuses production, remote databases, wrong database/role, query URL
overrides, superusers and non-18 servers before migrations. It applies real
migrations and creates unique synthetic identities, a verified Owner/Host, active
Pet and published Listing. A random password is Argon2-hashed. A mode-600 ignored
manifest exists only for the run. Cleanup deletes only those exact synthetic
identities and their resources in one transaction, never truncates tables, and
rolls back rather than expanding its scope on foreign dependencies/media. Normal
completion cleans up even on test failure. A hard process kill can leave a fixture;
keep the manifest private and recover with `APP_ENV=test E2E_DATABASE_URL=...`
`python -m tools.e2e_data cleanup /absolute/path/to/manifest` from backend.

Ports 8013/4173 must be free: existing servers are never reused. Playwright manages
and SIGTERM-stops both servers; Chromium is bundled/headless/project-local, never
installed Chrome. Screenshots, traces and video are disabled. Failure text may
contain a synthetic login password; `e2e-results` is ignored and not uploaded by
CI. Delete ignored failure output after diagnosis. No real credentials belong in
fixtures or test output. One worker avoids fixture races; this is a small smoke
suite, not replacement coverage for lower-level security/concurrency tests.

## Health, schema and lifecycle

- `GET /health`: process liveness, always `{ "status": "ok" }`, no database/provider call.
- `GET /ready`: 200 `{ "status": "ready" }` only when PostgreSQL responds and its
  Alembic revision set equals the packaged heads; otherwise 503 `not_ready`.
  Connection timeout is two seconds, SQL timeout one second, no provider calls.
- Neither exposes database URLs, SQL, credentials or exceptions. Probe readiness
  modestly (e.g. every 15 seconds), not on every user request.
- Production lifespan checks schema readiness and refuses startup if incompatible.
  Development can start before PostgreSQL; readiness still reports failure.
- Shutdown disposes SQLAlchemy's engine. SIGTERM is the deployment stop signal.
  No worker runs migrations implicitly.

Deployment order: back up/verify restore → install release dependencies → run
`python -m alembic upgrade head` ONCE with a migration role → start the new app →
check `/ready` → route traffic. Prefer a separate least-privilege runtime role with
SELECT/INSERT/UPDATE/DELETE on application tables and read access to alembic_version;
the migration owner handles DDL. Grant UUID/extension/schema permissions explicitly
as appropriate. Do not blindly downgrade a database during rollback: deploy a
compatible previous application or perform a reviewed recovery migration. Exact-head
startup checks require coordinated releases; this is not a zero-downtime expandable
schema deployment system.

## Safe production configuration

Set `APP_ENV=production`, `SESSION_COOKIE_SECURE=true`, `DEBUG=false`, a dedicated
non-test database URL with a non-placeholder password (minimum 16 characters),
explicit HTTPS `BACKEND_CORS_ORIGINS` JSON list and explicit `ALLOWED_HOSTS` JSON
list. No wildcard/localhost origins/hosts, postgres superuser name, test/dev/e2e
database name or TEST_DATABASE_URL is accepted. Length/placeholder checks are
configuration guardrails, not a claim of measured password entropy. Actual DB role
privileges and TLS must also be configured operationally.

Stripe/Cloudinary are optional: omit ALL of a provider's settings to disable it.
When configured in production, partial/obviously placeholder provider settings are
refused. Payments remain sandbox/test-only under the established payment policy.
Production-shaped deployment is not permission to charge real customers. Secure
cookies, no debug tracebacks, exact-origin CSRF/CORS and ownership checks remain
mandatory. There is no shared session-signing secret: opaque session/verification
nonces are random and only their hashes are persisted.

Vite exposes only `VITE_` variables: `VITE_STRIPE_PUBLISHABLE_KEY` is intentionally
public; database, Stripe secret/webhook and Cloudinary admin keys must never use
that prefix. API requests use relative `/api/v1`; the preferred topology is one
HTTPS origin with `/api`, `/health`, `/ready` proxied to FastAPI and SPA fallback
for other paths. No backend-secret bundling or runtime `.env` serving is allowed.
A different-origin deployment must update API routing, exact allowed origins,
Stripe return URLs and cookie SameSite topology deliberately; cross-site cookies
are not enabled by this milestone. Local Vite stays same-origin via its proxy.

## Server and edge contract

From backend, under a supervisor/non-root service account (not `--reload`):

```sh
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
  --workers 1 --no-access-log --proxy-headers --forwarded-allow-ips=127.0.0.1 \
  --log-config ../deploy/logging.json --timeout-graceful-shutdown 30
```

One worker is an intentional starting point; add workers after measuring load.
Only the trusted loopback proxy may reach the backend; do not trust arbitrary
forwarded headers. Terminate TLS, redirect HTTP to HTTPS, and enforce HSTS at the
public ingress. Build frontend using `npm ci && npm run build`; deploy `dist`
with SPA fallback, long immutable caching for hashed assets, short/no cache for
index.html, and never expose root `.env` or repository files. No Dockerfiles were
added: the native locked install and CI service container cover reproducibility
without an untested application-container deployment claim. No Docker daemon or
GUI is needed for local checks.

`deploy/nginx.conf` and `deploy/pawtel-proxy.conf` are a concrete adaptable example,
NOT a deployed proxy. Copy proxy include to its declared path, choose actual
server/domain/static-root/TLS ingress and validate with `nginx -t`. The example
listener is loopback-only behind a trusted TLS ingress. All public traffic MUST
traverse that edge. It overwrites forwarding chains and bounds body/time sizes.
Do not deploy its example hostname unchanged.

Rate protection is an EDGE CONTRACT, not a hidden per-worker Python dictionary:
login/register/verification 10/minute/IP + burst5, Checkout 10/minute + burst3,
media 6/minute + burst2, 429 on excess. Nginx zones coordinate its workers, not
separate edge instances. Multiple edges need shared/platform protection; NAT users
can share limits, and IP limits alone do not stop credential stuffing/botnets.
No distributed guarantee, account lockout or Redis is claimed. Native direct
Uvicorn development has no rate limiter. The production ingress must provide
metrics/alerts and privacy-safe 429 reporting, without credential-bearing URLs.

The ASGI application bounds actual received bytes, including chunked bodies,
before downstream JSON/media parsing: JSON 64KiB, Stripe webhook 1MiB, raw media
5MiB. Existing image decoding/dimension/type limits still apply. The edge also
bounds bodies, slow uploads and connection resources; the application alone cannot
fully protect against slow clients or massive concurrent small bodies. Preserve
raw webhook bytes for signature verification. Generic 413 errors are safe and
correlated. Timeouts/body limits must be aligned with deployment ingress settings.

Security headers include nosniff, strict-origin referrer policy, framing denial,
restricted camera/microphone/geolocation and HSTS for production API responses.
CSP groundwork only sets frame-ancestors/base-uri/object-src; it deliberately does
not restrict Stripe scripts/child frames or Cloudinary delivery. Apply equivalent
headers to static HTML at the edge. A final restrictive CSP requires actual Stripe
and media domain inventory and manual sandbox testing; no complete CSP is claimed.

## Logging and diagnosis

Application events are JSON lines with UTC timestamp, level, allowlisted event,
request ID, method, matched route TEMPLATE, status and duration. Raw path IDs,
queries, request/response bodies, cookies, CSRF values, webhook signatures, provider
credentials and client secrets are never included. Only canonical UUID request IDs
are preserved (case normalized); missing/invalid/duplicate IDs are replaced. They
are returned as `X-Request-ID`, exposed through exact-origin CORS, and safe API
errors show that reference in private-page UI. IDs are diagnostics, not identity.

The formatter drops arbitrary message/argument/exception text, including Uvicorn
traceback values. Unexpected/database/readiness failures record exception TYPE and
safe HTTP context. This trades detailed stack text for credential safety; diagnose
with matched events, regression tests and controlled local reproduction. Do not
add raw provider exception strings or HTTP body debug logging. The supplied log
configuration formats Uvicorn lifecycle events too; `--no-access-log` avoids a
second raw URL access log. Application middleware replaces it with safe request
events. Restrict log access/retention. Third-party debug logging must stay disabled.
The example edge replaces raw access logs with JSON method/status/duration/upstream
status/request-reference events (no URL/IP/headers), including edge-only 429/413
failures. Raw nginx error output is suppressed because its format can include
queries; deploy filtered counters/alerts and restricted redacted diagnostic error
collection before launch. Safe request events replace the lost access information.

## Launch gaps

No production rollout, security audit, dependency
vulnerability clearance, performance/load test, uptime alerting, backup restore
drill, distributed rate limiter or final restrictive CSP is claimed. A real launch
also needs real email verification delivery, customer support/reconciliation
operations, privacy/retention/legal review, provider access controls, backup and
incident procedures. Existing payment reconciliation/media cleanup commands need
an operator or scheduled job; they are not silently run by health/startup.

## Official references used

- [GitHub PostgreSQL service containers](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers)
- [Workflow permission syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)
- [Playwright CI](https://playwright.dev/docs/ci-intro) and [managed web servers](https://playwright.dev/docs/test-webserver)
- [Uvicorn deployment](https://uvicorn.dev/deployment/) and [settings](https://uvicorn.dev/settings/)

The command above uses the existing Uvicorn dependency under an external supervisor;
it does not add Gunicorn or the deprecated `uvicorn.workers` integration. Reload is
reserved for local development.

## Dependency review observed locally

The 13 November 2026 `npm audit --json` recheck reported 11 affected development
dependency entries: 10 moderate through the ESLint/typescript-eslint → minimatch
chain, and one high through jsdom → undici 7.30.0. These are npm dependency findings,
not a count of distinct CVEs. `npm ls undici minimatch --all` confirmed those paths.
A separate `npm audit --omit=dev --json` reported zero production-dependency
advisories at the time checked. That result is not a vulnerability-free guarantee.
These test/lint tooling findings remain unresolved; review compatible upstream fixes
as a focused dependency task. Suggested broad/downgrade/`--force` fixes were not
applied because they can break the established ESLint 10/TypeScript 6 toolchain.
No Python vulnerability audit was performed; `pip check` checks consistency only.

## Selected hosted path (Milestone 14)

The [deployment guide](deployment.md) supersedes the generic Nginx example for the
selected Render portfolio deployment. React and FastAPI share one web service;
Render handles HTTPS, while application headers and explicitly single-process
aggregate demo budgets remain server-side. The old Nginx example is not deployed.

## Static showcase verification

The frontend CI job also builds and runs the [synthetic showcase](frontend-showcase.md)
with bundled headless Chromium and no backend/database/provider. Its network/storage
checks complement the existing isolated full-stack E2E job; they do not replace it.
Use `cd frontend && npm run test:showcase` after the documented browser installation.

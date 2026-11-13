# Portfolio deployment: Render, one HTTPS origin

Status: repository preparation only. **No public deployment URL has been verified.**
Do not advertise PAWTEL as live until the smoke checks below pass. No account,
subscription, DNS or remote resource was changed by the implementation agent.

## Decision and current provider research (12 November 2026)

Use **one paid Render Web Service** to serve compiled React and FastAPI, plus
**paid Render PostgreSQL 18 in Singapore**. Keep existing Cloudinary and Stripe
sandbox boundaries. This is a small modular monolith, not a new frontend platform.

| Evaluated option | Current evidence and trade-off |
| --- | --- |
| Render static frontend | Free CDN hosting with Git integration, HTTPS and SPA rewrites; a separate origin adds cookie/proxy/domain complexity ([docs](https://render.com/docs/static-sites)) |
| Vercel Hobby frontend | $0 personal/non-commercial tier; appropriate for a portfolio, but another service/origin provides little benefit here ([plan](https://vercel.com/docs/plans/hobby)) |
| Cloudflare Pages | Free allowance includes 500 builds/month; global frontend delivery, still requires deliberate API topology ([limits](https://developers.cloudflare.com/pages/platform/limits/)) |
| Render backend | Python 3.14 supported, managed HTTPS, paid pre-deploy hook, persistent process; selected for simple operation ([Python](https://render.com/docs/python-version), [release hook](https://render.com/docs/deploys#pre-deploy-command)) |
| Railway backend | $5/month minimum Hobby usage with $5 credit, then metered resource usage; viable but less predictable fixed-small-demo pricing ([pricing](https://railway.com/pricing)) |
| Render PostgreSQL | PG18 available, same-region private network, paid backups; one hosting account ([database docs](https://render.com/docs/postgresql-creating-connecting)) |
| Neon PostgreSQL | Free: 100 CU-hours/project/month and 1GB/project currently advertised; useful alternative, adds provider/network and scale-to-zero assumptions ([pricing](https://neon.com/pricing)) |

Singapore is the available Render APAC region, not an Australian data residency
claim. Keep app and database together; measure Australian latency after deployment.
Serving the SPA from the app trades a separate global HTML/assets CDN for one origin
and atomic UI/API releases. Cloudinary still delivers photos from its CDN.

### Cost: review before creating anything

Checked 13 November 2026: the official page lists Hobby workspace at $0 plus
compute, **US$7/month** for `0.5c-512mb`, **US$6/month** for `0.1c-256mb`, and 1GB
PostgreSQL SSD included. The selected 1GB baseline is **US$13/month before tax and
metered extras**; additional storage is advertised at **US$0.30/GB-month**. Review
the actual creation quote, usage/build/bandwidth limits and any optional workspace
upgrades yourself. This is not a guaranteed invoice or AUD conversion.
[Official pricing](https://render.com/pricing), [plan IDs](https://render.com/docs/compute-plans).

A free Render web service sleeps after 15 idle minutes and can take about one
minute to wake; free PostgreSQL expires after 30 days and lacks recovery. It is
not the recommended persistent recruiter link. Paid services enable the explicit
release hook. Hobby workspace and paid compute are different billing dimensions.
[Free limitations](https://render.com/docs/free).

Cloudinary has a free allowance; monitor its credits/storage/delivery limits and
keep uploads private to invited synthetic Hosts. Stripe stays sandbox/test-only;
no real payment-processing revenue/fees are assumed. Custom domains, paid media,
more compute/storage or a higher workspace tier are optional, never provisioned
here. Set spending alerts/limits available in your provider account yourself.

See the definitive [environment inventory](deployment-environment.md) and
[numbered manual deployment procedure](deployment-preflight.md), including cost,
retirement and acceptance gates. They refine the checklist without provisioning anything.

## 1. Review CI and release code

Milestone 13 is commit `ec28a9d33574640b76f718d5eafeb0af1d1a3706`.
The [first run](https://github.com/doyosogo/Pawtel/actions/runs/43130211923) completed
with frontend success, backend test failure and E2E skipped. Public job metadata
was readable, but detailed logs returned 403; existing gh authentication was
invalid and was not changed. Local CI-style reproduction identified two fixtures
inheriting TEST_DATABASE_URL into production settings, plus a no-database readiness
test inheriting DATABASE_URL. They now explicitly isolate those settings. Production refusal remains intact. This is an environment-isolation bug, not
proof of a Linux-specific Python defect. Those fixes were committed/pushed as
`a8faa4f5a4b421001960b3c5bb58804f6b526d77`. On 13 November 2026,
[run 43312304584](https://github.com/doyosogo/Pawtel/actions/runs/43312304584)
was verified successful on GitHub-hosted Linux: frontend, backend and E2E all passed.
No workflow was rerun/cancelled/modified by the agent. This records a remote CI
baseline, not a deployed release; future commits need their own checks.

Latest preflight baseline: [run 43317246922](https://github.com/doyosogo/Pawtel/actions/runs/43317246922)
for `da2255d` is also fully green (checked 13 November 2026).

Local checks and remote CI are separate evidence. Do not deploy until all three
GitHub jobs pass for the exact commit you intend to release.

## 2. Create the selected infrastructure yourself

1. Review `render.yaml` and the price estimate. It declares PAID resources. Create
   your own Render account/workspace if needed; the agent must not do this.
2. Connect your GitHub repository manually. Review permissions; do not add provider
   write secrets to ordinary PR CI. Select the reviewed commit/branch.
3. Use a Blueprint from the repository root, or enter its exact settings manually.
   Keep root directory **blank**: both frontend and backend must be available.
4. Create PostgreSQL **18**, Singapore, database AND role **pawtel_portfolio**,
   `0.1c-256mb`, 1GB storage. Do not use an existing real-user database. External
   IP allow list is empty in the Blueprint, disabling external access. Internal
   same-region access remains available. Do not enable storage autoscaling blindly.
5. Create the web service in Singapore, `0.5c-512mb`, exactly **one instance** and
   one worker, Python runtime. Auto-deploy is **Off**. Applying a Blueprint may
   initiate its first deployment; do so only after reviewing settings/cost.
6. Copy the ACTUAL assigned HTTPS service origin and hostname; do not assume the
   example service name is available. Supply the JSON settings below before a
   successful release. No fabricated URL is provided in this document.

## 3. Environment and secrets

Configure only in Render's service environment/secret store. Do not print or commit
values. The root `.env` is ignored and remains for native local development.

| Variable | Deployment value / purpose |
| --- | --- |
| PYTHON_VERSION | `3.14.8`, pinned to verified local patch |
| NODE_VERSION | `24.13.1`, pinned for the frontend build |
| APP_ENV | `production` |
| DEBUG | `false` |
| SESSION_COOKIE_SECURE | `true` |
| SERVE_FRONTEND | `true`; requires compiled frontend/dist |
| PORTFOLIO_DEMO | `true`; registration disabled by server, demo notices/budgets enabled |
| DATABASE_URL | Blueprint's private connection string; never VITE_ |
| BACKEND_CORS_ORIGINS | JSON list with ONLY the actual HTTPS browser origin, no trailing slash |
| ALLOWED_HOSTS | JSON list with actual service hostname; add verified custom hostname only if used |
| PAWTEL_DEMO_PASSWORD | Private 15–128 character synthetic-account passphrase, operator seed only |
| STRIPE_SECRET_KEY | Optional sandbox/test secret only |
| STRIPE_WEBHOOK_SECRET | Optional secret for THIS deployed sandbox webhook destination |
| STRIPE_RETURN_URL | Actual HTTPS origin + `/checkout/return`, no query/fragment |
| VITE_STRIPE_PUBLISHABLE_KEY | Optional public sandbox key from same Stripe account, set BEFORE build |
| CLOUDINARY_CLOUD_NAME | Optional dedicated media environment cloud name |
| CLOUDINARY_API_KEY | Optional server credential |
| CLOUDINARY_API_SECRET | Optional server credential |

**Omit TEST_DATABASE_URL entirely** in production. Omit ALL Stripe settings until
payments are configured; likewise omit all Cloudinary settings until media is
configured. Do not copy local `.env` wholesale. Never put admin/database/webhook
secrets under VITE_. No GitHub deployment write secret is needed: CI only checks;
you manually deploy through Render. Do not create competing public API URL settings.

### Database URL, TLS and connections

Render's standard postgres/postgresql URL is normalized to SQLAlchemy's
`postgresql+psycopg` driver, preserving percent-encoded passwords/query settings.
Production defaults missing sslmode to `require`, refuses plaintext/fallback modes,
and preserves explicit verify-ca/verify-full. Render internal certificates are
self-signed: its documented internal TLS option is `require`, not verify-full.
This encrypts private-network transport but does not claim CA/hostname verification.
Do not disable TLS. External administration needs the full external hostname,
provider TLS requirements and a narrowly allowed operator IP if temporarily enabled.
[Render TLS policy](https://render.com/docs/postgresql-creating-connecting#ssl-modes-for-internal-connections).

Application pool: two persistent connections, two overflow, five-second pool wait,
pre-ping, five-minute recycle and bounded connect timeout. Readiness/migrations use
short-lived connections. No PgBouncer transaction-mode assumptions or unverified
pooler configuration. READ COMMITTED and Booking locking remain unchanged. Avoid
scaling workers before budgeting database connections; credentials/role privileges
must be reviewed separately. The Blueprint's database owner is also the small-demo
migration/runtime identity; separate DDL and runtime roles remain a real-launch task.

## 4. Build, migrate, start

Render settings are checked into `render.yaml`:

- Build: `bash deploy/render-build.sh` — installs the backend snapshot/editable
  package and runs frontend `npm ci --include=dev` plus TypeScript/Vite build, including build tools
  even when NODE_ENV=production.
- Pre-deploy: `cd backend && python -m tools.validate_deployment && python -m alembic upgrade head`.
- Start: `bash deploy/render-start.sh` — bind `0.0.0.0:$PORT`, one worker, no reload,
  safe JSON logging, bounded concurrency and graceful shutdown.
- Health check: `/ready`. This prevents routing to a release with an unavailable
  DB/schema. Render also restarts unhealthy instances, so a prolonged database
  outage can cause restarts; `/health` stays a separate diagnostic liveness route.
  No Stripe/Cloudinary probes. [Platform behavior](https://render.com/docs/health-checks).

The paid pre-deploy hook runs once per deployment, independently of workers. Failed
migration stops rollout; old app may still be running, so migrations must be backward
compatible. Startup never silently migrates. Native local development commands and
its separate PostgreSQL databases continue unchanged.

### Cookies, CSRF, proxy and SPA

React/API share the same origin. The typed client has one relative `/api/v1` base;
Vite still proxies only during development. No absolute backend URLs are scattered
through components, no VITE_API_BASE_URL is needed. Cookies remain HttpOnly, Secure,
SameSite=Lax, host-only, Path=/ with the __Host- prefix in production. CORS, Origin,
custom request header and synchronizer CSRF rules remain. Different unrelated
frontend/backend provider subdomains are NOT a supported copy/paste alternative;
SameSite=None was not enabled.

Render terminates HTTPS and supplies the public Host. The start command deliberately
uses `--no-proxy-headers`: there is no need to trust arbitrary forwarded client IPs
or infer cookie security/return URLs from request scheme. Do not add wildcard proxy
trust without a verified platform boundary. API slash redirects are disabled to
avoid generated internal-http redirects; clients use canonical endpoint paths.

Compiled assets and SPA fallback are served only from frontend/dist. Direct route
refreshes return index.html; API/diagnostic paths never become HTML fallbacks.
Missing assets and hidden/traversal paths return 404. Hashed assets are immutable;
SPA navigation HTML is no-store. No source files/root .env are served. FastAPI's
security headers now cover both HTML and API, avoiding two layers of duplicate
header configuration. CSP remains groundwork, not a claimed final Stripe-tested CSP.

## 5. Prepare safe synthetic access

Public visitors may browse. **Do not publish shared mutable credentials** on the
homepage/README. Privately give a recruiter temporary synthetic access, then rotate
it after the demonstration. No real Pet/owner/contact information belongs here.

After migrations, use Render's shell yourself, from repository root:

```sh
cd backend
PORTFOLIO_SEED_CONFIRM=pawtel_portfolio python -m app.scripts.seed_portfolio
```

The private PAWTEL_DEMO_PASSWORD must already be configured. The CLI requires
production + PORTFOLIO_DEMO + exact dedicated TLS database/role + explicit operator
acknowledgement, checks actual DB identity/non-superuser, and refuses any unrelated
User rows before modifying anything. It creates/reuses the fixed fictional
`workflow.owner@pawtel.example.com` and `workflow.host@pawtel.example.com`, verified
synthetic accounts, DOG/CAT Pets and a published Listing. No Bookings are seeded.
Normal registration/verification remains unchanged outside portfolio mode.

This is **idempotent setup/password rotation, not a destructive reset**. Changing
the private password then rerunning revokes synthetic sessions. It preserves edited
Pets/Listings and history; it does not erase Booking/payment/media records. Existing
local-only seed guards are untouched. No unauthenticated reset endpoint or automatic
production deletion exists. After a demonstration, rotate access, run existing
expiry/reconciliation/media cleanup commands as appropriate, review synthetic data
privately and use a separately reviewed restore/reseed procedure if needed. Keep
provider media cleanup consistent with DB restoration; do not orphan cloud assets.
There is no scheduled general reset or promise of unlimited garbage-data cleanup.

Portfolio mode disables registration server-side and communicates that email is
not sent. Login remains normal Argon2/session authentication. Verification tokens
are never exposed. A banner labels fictional stays, synthetic data and test charges.

### Abuse boundaries

Render provides general edge DDoS protection; its API rate limit is NOT protection
for your application routes. No documented configurable per-route Render edge WAF
is assumed. [Render guidance](https://render.com/docs/ddos-protection).

For this single-instance/single-worker demo only, aggregate application budgets
bound auth attempts (10/minute), checkout starts (10/minute), image uploads
(6/minute), plus at most two concurrent auth handlers. They use no forwarded IP
and bounded state. Excess gets 429/Retry-After. They are shared across visitors,
reset on restart, and are NOT distributed, per-account or bot-proof; visitors may
exhaust the shared budget. Webhooks, logout and diagnostics are not throttled by
these budgets. Body caps remain JSON64KiB/webhook1MiB/media5MiB. Do not scale out
without replacing budgets with a true shared/edge policy. An untrusted high-traffic
service needs stronger abuse protection; private credentials reduce demo exposure.
The older Nginx template is NOT running on Render and is not claimed as protection.

## 6. Stripe sandbox and Cloudinary — manual provider actions

Stripe: select your sandbox/test environment yourself. Never switch to live mode.
Use its sandbox secret and public publishable key in the locations above. In
Workbench → Webhooks/Event destinations create a destination for the actual public
HTTPS URL `/api/v1/webhooks/stripe`. Choose snapshot events for
`checkout.session.completed` and `checkout.session.expired`; align with the backend's
pinned `2026-10-28.endive` API contract. Set THIS destination's signing secret in
Render; a local Stripe CLI listener secret is different. Set the HTTPS return URL,
rebuild for the public key, and redeploy yourself. No deployed CLI forwarding is
needed because Stripe can reach the public endpoint directly. Browser returns
remain neutral and refetch the backend. Only verified webhooks confirm Bookings;
late payment after cancellation remains reconciliation, never resurrection.
[Official endpoint setup](https://docs.stripe.com/webhooks).

Cloudinary: create/select a dedicated demo product environment yourself, keep admin
credentials server-side, configure the three names above, redeploy. Login as Host,
upload a synthetic JPEG/PNG/WebP under 5MiB, publish and verify public CDN delivery.
Current app limits are six images/Listing, 200–6000px each dimension and 24M pixels.
Effective upload maximum is the lowest of app 5MiB, your Cloudinary account limit
and platform ingress policy. No authoritative lower Render ingress cap was found;
DO NOT assume unlimited ingress. Verify a near-limit synthetic file manually after
deployment and keep provider limits at least 5MiB. No external upload was performed.
[Server upload documentation](https://cloudinary.com/documentation/upload_images).

## 7. Read-only smoke and your manual acceptance checklist

From backend with the project environment active, replace the example origin:

```sh
python -m tools.deployment_smoke --frontend https://YOUR_ACTUAL_SERVICE.onrender.com
```

Same-origin backend is the default; optional `--backend` supports diagnostics, not
a claim of supported cross-site authentication. TLS stays verified. The script
performs only bounded anonymous GETs: compiled React HTML, health, readiness and
public discovery. It rejects credentials/query/path origins, follows no redirects,
prints no response bodies/secrets, exits nonzero on failure. Empty discovery is
valid; seed content separately. `--allow-local-http` is explicit and loopback-only.

Personally test homepage/search/images, private-route redirect, security headers present once on HTML/API, invited Owner
login/Pets/request, Host inbox/accept, Owner AWAITING_PAYMENT, deadline/price,
sandbox Checkout/decline/retry/webhook CONFIRMED when configured, Host draft/edit/
publish/photo/archive, refresh a deep route, logout/back navigation, mobile layout
and keyboard focus. Check `/health`, `/ready`, safe request references and demo
registration refusal. Do not use real customer/card information. Do not advertise
the live link until smoke and these checks pass.

## 8. Logs, backups, rollback and troubleshooting

Render's built-in Logs page shows JSON stdout/stderr. Search by the user-visible
request UUID, then inspect event/method/template/status/duration/exception type.
Use deploy logs for safe configuration diagnostics and migration/startup failures;
use `/ready` status for DB/schema problems. No paid observability service is added.
Platform logs have their own retention/privacy; do not enable body/provider debug
logs or expose logs to recruiters. [Built-in logs](https://render.com/docs/logging).

Paid PostgreSQL on Hobby currently includes a **three-day PITR window**; Pro+
workspace extends to seven days. Recovery creates another DB instance, which you
must validate and repoint manually, potentially adding cost. Free databases have
no recovery. This is not proof of your own restore drill; take/review logical
exports before risky operations and protect their secrets/private contents.
[Backup policy](https://render.com/docs/postgresql-backups).

Rollback UI/API together by choosing a known-good Render deploy/commit manually;
auto-deploy stays Off. Environment changes and database writes are not undone by
code rollback. For additive DDL prefer a compatible older application or forward
fix; don't blindly alembic downgrade. Exact-head startup checks mean a schema
rollback/forward compatibility plan must be reviewed, not assumed. Preserve payment
receipts/attempts and reconcile provider state before restoring database history.

Troubleshooting: root blank/build missing → inspect build script; failed settings
→ safe validator and names above; startup/schema → pre-deploy logs/Alembic head;
login/CSRF → exact public Origin, host-only Secure cookie and no foreign frontend
origin; payment → same sandbox/destination secret/event version/return URL; media
→ server credentials/account quota/body limit; 429 → shared demo budget, wait;
503 under load → bounded concurrency/DB readiness, inspect logs before scaling.

No deployment secrets belong in source or ordinary GitHub PR CI. This guide is the
single selected path; final provider purchase/account choices remain yours.

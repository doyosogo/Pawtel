# Definitive deployment environment inventory

Checked against `Settings`, seed/operator tools, Vite usage and `render.yaml` during
Milestone 16. Formats below are templates, NOT usable secrets or invented live URLs.
Use Render's **Web Service Environment** for app/build values; ordinary GitHub PR CI
needs no deployment secrets. Never copy the local `.env` wholesale into Render.

## Required for the selected portfolio deployment

“Required” includes the selected safety/topology contract: some flags have defaults
that allow an API-only/non-demo application to start, but do not deliver the intended
public synthetic demo. DATABASE_URL/origins/hosts are also enforced by production
validation; PORT is required by the start script.

| Exact name           | Safe format / selected value                                                                 | Visibility            | Web Service needs it?    | Supplied by PostgreSQL?                        | Manual action                                                                     |
| -------------------- | -------------------------------------------------------------------------------------------- | --------------------- | ------------------------ | ---------------------------------------------- | --------------------------------------------------------------------------------- |
| APP_ENV              | `production`                                                                                 | Public config         | Runtime                  | No                                             | Blueprint fixes value; do not override to development                             |
| DATABASE_URL         | `postgresql://pawtel_portfolio:<encoded-provider-password>@<internal-host>/pawtel_portfolio` | Secret                | Runtime + migration      | Yes, Blueprint `fromDatabase.connectionString` | Create selected DB yourself; keep generated binding, do not paste a different URL |
| BACKEND_CORS_ORIGINS | `["https://<actual-service-host>"]`                                                          | Public                | Runtime                  | No                                             | Paste exact browser HTTPS origin JSON, without trailing slash                     |
| ALLOWED_HOSTS        | `["<actual-service-host>"]`                                                                  | Public                | Runtime/health probe     | No                                             | Paste actual hostname JSON; no scheme, path, wildcard or localhost                |
| SERVE_FRONTEND       | `true`                                                                                       | Public config         | Runtime                  | No                                             | Blueprint fixes value; compiled frontend/dist must exist                          |
| PORTFOLIO_DEMO       | `true`                                                                                       | Public config         | Runtime + portfolio seed | No                                             | Blueprint fixes value; disables public registration, enables demo notices/budgets |
| PORT                 | Provider-assigned integer                                                                    | Public infrastructure | Start script             | No                                             | Render supplies automatically; do not hard-code or paste a local port             |

If the assigned hostname is not yet visible during initial Blueprint creation,
finish creating the resources yourself, then set the ACTUAL origin/hostname before
a successful release. An initial missing-config attempt fails closed; never use a
wildcard to make health checks pass. The public site has one origin; there is no
PUBLIC_FRONTEND_URL or VITE_API_BASE_URL to invent or synchronize.

## Required only when the feature/operator action is enabled

Omit the entire Stripe or Cloudinary group until configured. Do not leave a local
Stripe return URL configured with missing credentials in production.

| Exact name                  | Safe format                                                            | Visibility                          | Where / Web Service usage                                            | PostgreSQL supplies it? | What you must create manually                                                       |
| --------------------------- | ---------------------------------------------------------------------- | ----------------------------------- | -------------------------------------------------------------------- | ----------------------- | ----------------------------------------------------------------------------------- |
| STRIPE_SECRET_KEY           | `sk_test_<sandbox-key>` (supported restricted test keys also accepted) | Secret                              | Runtime server only                                                  | No                      | Select sandbox; copy its test API key privately                                     |
| VITE_STRIPE_PUBLISHABLE_KEY | `pk_test_<sandbox-public-key>`                                         | Public                              | Web Service **build-time**, compiled into React                      | No                      | Same sandbox's publishable key; rebuild after changing                              |
| STRIPE_WEBHOOK_SECRET       | `whsec_<destination-signing-secret>`                                   | Secret                              | Runtime server only                                                  | No                      | Create THIS HTTPS sandbox event destination, copy its signing secret                |
| STRIPE_RETURN_URL           | `https://<actual-service-host>/checkout/return`                        | Public                              | Runtime checkout creation                                            | No                      | Set actual same-origin HTTPS path, no query/fragment                                |
| CLOUDINARY_CLOUD_NAME       | `<your-demo-cloud-name>`                                               | Public identifier, kept server-side | Runtime media adapter                                                | No                      | Select/create dedicated demo product environment yourself                           |
| CLOUDINARY_API_KEY          | `<provider-api-key>`                                                   | Server credential                   | Runtime server only                                                  | No                      | Copy privately from that product environment                                        |
| CLOUDINARY_API_SECRET       | `<provider-api-secret>`                                                | Secret                              | Runtime server only                                                  | No                      | Copy privately; never any VITE_ storage/admin credential                            |
| PAWTEL_DEMO_PASSWORD        | `<your-private-15-to-128-character-passphrase>`                        | Secret                              | Operator seed/rotation only; normal API auth uses stored hashes      | No                      | Choose/store privately before operator seed; never publish it                       |
| PORTFOLIO_SEED_CONFIRM      | `pawtel_portfolio`                                                     | Non-secret acknowledgement          | Operator shell inline, not a frontend value or normal Settings field | No                      | Supply only when intentionally running seed command; do not persist as a credential |

The three backend Stripe values must be complete to enable server checkout. The
publishable key is additionally needed by React. The service can start with Stripe
and media disabled, and still browse/request/accept synthetic stays. No live keys.
`PAWTEL_DEMO_PASSWORD` is not printed or persisted as plaintext by the seed. A provider
secret store retains the operator-supplied value; PostgreSQL holds Argon2id hashes.
Rotate it after sharing invited access, rerun seed to revoke synthetic sessions.

## Optional safe overrides / defaults

All belong to the Web Service if overridden; none are supplied by PostgreSQL or
need manual secret creation. Blueprint pins explicit safety/runtime values where
shown. Defaults are not permission to enable debug or insecure production cookies.

| Exact name                     | Default / Blueprint value | Visibility and usage                                                                                                                                                                     |
| ------------------------------ | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| APP_NAME                       | `PAWTEL API`              | Public title                                                                                                                                                                             |
| DEBUG                          | `false`                   | Public setting; production rejects true, app never returns debug traces                                                                                                                  |
| SESSION_COOKIE_SECURE          | `true`                    | Public policy; production rejects false                                                                                                                                                  |
| SESSION_LIFETIME_SECONDS       | `86400` (300–604800)      | Public policy, runtime                                                                                                                                                                   |
| BOOKING_PAYMENT_WINDOW_SECONDS | `1800` (60–86400)         | Public policy, runtime authoritative deadline                                                                                                                                            |
| VERIFICATION_LIFETIME_SECONDS  | `86400` (300–172800)      | Public policy; does not add email delivery                                                                                                                                               |
| PYTHON_VERSION                 | Blueprint `3.14.8`        | Render runtime/build selection; keep pin, not an app secret                                                                                                                              |
| NODE_VERSION                   | Blueprint `24.13.1`       | Render frontend-build runtime selection; keep pin                                                                                                                                        |
| NODE_ENV                       | May be `production`       | Node tooling policy; build explicitly installs dev build tools with `npm ci --include=dev`                                                                                               |
| STRIPE_PUBLISHABLE_KEY         | Unset recommended         | Legacy **backend validation-only** alias; not consumed by Checkout/React. Kept accepted for compatibility, not required or renamed. Use only VITE_STRIPE_PUBLISHABLE_KEY for the browser |

No SESSION_SECRET/JWT_SECRET is required: sessions use random opaque credentials
whose hashes are stored in PostgreSQL. Do not create undocumented secrets.

## Local/test/runner values — never deploy these

| Exact name               | Purpose / safe format                       | Production rule                                            |
| ------------------------ | ------------------------------------------- | ---------------------------------------------------------- |
| TEST_DATABASE_URL        | Local/CI guarded `pawtel_test` psycopg URL  | **Omit entirely**, not an empty DSN; production refuses it |
| E2E_DATABASE_URL         | Dedicated loopback `pawtel_e2e` DB/role URL | E2E only; never the deployed DB                            |
| PAWTEL_E2E_PYTHON        | Test-runner Python executable path          | Runner-owned, omit                                         |
| PAWTEL_E2E_FIXTURE       | Private ignored synthetic manifest path     | Runner-owned, omit                                         |
| PAWTEL_API_PROXY_TARGET  | Vite test proxy URL                         | E2E only; production uses relative /api/v1                 |
| PLAYWRIGHT_BROWSERS_PATH | Ignored project-local browser cache         | Test installation/runner only                              |

Local `.env.example` intentionally chooses development HTTP cookies, local return
URL and local databases. Preserve those local defaults; the deployment inventory
and Blueprint define production values. Any VITE_ variable is public build data:
never place database URLs, passwords, Stripe secret/webhook keys, Cloudinary admin
credentials or seed passwords under VITE_.

The separate static Vercel showcase uses only the committed public
`VITE_PAWTEL_SHOWCASE=true` in `frontend/.env.showcase` and Vite showcase mode.
Do not add that flag to Render or ordinary local environments. See
[frontend showcase](frontend-showcase.md); it is not another backend deployment setting.

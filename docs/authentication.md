# Authentication and security: Milestone 3

Implemented: registration, Argon2id password storage, opaque PostgreSQL sessions,
logout, self lookup, session-bound CSRF, verification-token issuance/consumption and
safe errors. There is **no email provider**, public resend endpoint, password reset,
OAuth, polished frontend, host onboarding or marketplace permission/workflow API.
This is a tested authentication foundation, not a claim of deployment readiness.

## Opaque sessions instead of JWTs

A login generates 32 random bytes using `secrets.token_urlsafe(32)` (43 URL-safe
characters). Only its purpose-separated SHA-256 digest is stored in auth_sessions;
the raw credential is sent only as an HttpOnly cookie. A database read therefore
does not directly yield replayable session cookies. Fast digest lookup is suitable
for uniformly random 256-bit tokens; it is **not** suitable for human passwords.
There is no custom cipher, signing scheme, JWT or Redis dependency.

Every authenticated request checks PostgreSQL for a matching, unrevoked, unexpired
session and its User. PostgreSQL is already required by this application and is
sufficient for its current scale. Immediate revocation and account-state checks are
simpler than JWT access/refresh-token revocation machinery. The trade-off is a
request-time database lookup and dependence on database availability. No measured
throughput claims are made. There is no sliding expiry or last-used write on GET.

Multiple active sessions are supported. Login never adopts an incoming credential
as its new token. Successful re-login with a valid current cookie rotates that
browser's session and CSRF nonce, revoking the old session in the same transaction;
other devices remain active. Expired/revoked/malformed/unknown credentials do not
authenticate. Existing Milestone 2 users have a nullable password_hash and cannot
password-login until a future explicit credential-setup process; no default password
or pretend credential was assigned during migration.

## Passwords and input contracts

argon2-cffi 25.1.0 supplies Argon2id with explicit parameters: 64 MiB memory, three
iterations, four lanes, 16-byte random salt and 32-byte hash. The encoded PHC value
contains the algorithm, parameters, salt and hash. Passwords are hashed, not
reversibly encrypted. The established library supplies hashing, verification and
rehash detection; the application does not implement Argon2 itself.

Registration accepts 15–128 Unicode code points, preserving spaces and Unicode
exactly. It has no uppercase/digit/symbol rules and never truncates or strips the
password. The minimum suits a passphrase-oriented single-factor login; the maximum
bounds hashing input and supports password managers. Login accepts 1–128 characters
and gives generic credential failure for incorrect short passwords. Request types
reject extra fields, bound display names and validate email syntax without external
DNS/deliverability calls. API email policy currently accepts ASCII addresses only;
whole-address trim/lowercase follows the existing account canonicalisation. Broader
internationalised-address support is deferred.

The service hashes before opening its write transaction. The User column stores
only the resulting hash. Its CHECK accepts null or an Argon2id prefix, but does not
pretend to validate a complete encoded hash: actual verification is the library's
job, and malformed hashes fail closed. Successful login can rehash an older valid
hash with the current parameters. Deployment hardware still needs load/memory
benchmarking before public traffic.

Wrong password, unknown email, null legacy hash and inactive-login rejection use
401 invalid_credentials. Missing accounts use a process-local dummy Argon2 hash
with the same parameters, so they do not simply skip expensive verification. This
reduces an obvious timing difference; it does **not** make timing indistinguishable
or authentication timing-attack proof. Registration's 409 duplicate response still
allows account-existence inference; that trade-off is explicit. Rate limiting and
abuse monitoring are required before public deployment and are not implemented here.

## Cookie configuration

| Setting | Actual behaviour |
|---|---|
| HttpOnly | Always true; JavaScript cannot read the session cookie. |
| Secure | True by default; may be false only outside production for local HTTP. |
| Name | `__Host-pawtel_session` when Secure, otherwise `pawtel_session`. |
| Domain | Omitted; host-only. The __Host- prefix additionally requires Secure and Path=/. |
| SameSite | Lax; useful cross-site mitigation, not the sole CSRF defence. |
| Path | `/`, including cookie deletion. |
| Max-Age / Expires | Fixed session lifetime; default 86400 seconds, matching database expiry. |

APP_ENV defaults to production. Production rejects insecure cookie settings and
non-HTTPS CORS origins. CORS defaults to no allowed origins; configured origins must
be exact HTTP(S) scheme/host/port values without wildcards or paths. The ignored
local .env and safe .env.example explicitly choose development and Secure=false.
Use localhost consistently rather than mixing localhost and 127.0.0.1 for browser
cookies. Production expects same-site frontend/API deployment under HTTPS; Lax
cookies are not a cross-site third-party-cookie deployment solution.

Never put session credentials in localStorage, sessionStorage, JSON responses or
URLs. HttpOnly reduces cookie theft through JavaScript, but an XSS payload can
still make requests as the user. TLS, XSS prevention and deployment hardening remain
necessary. Do not enable request-body, Cookie, Set-Cookie or SQL-parameter logging.

## CSRF: synchronizer token and login protection

Each session has an independently random 32-byte CSRF nonce. GET
/api/v1/auth/csrf returns it to an authenticated client. It is stored as a raw nonce
in that session row: unlike the HttpOnly session token, this value alone does not
authenticate and is not a substitute for a session cookie. Storing it lets reloads
and multiple tabs retrieve the same nonce without rotating it on every GET.
Authentication/CSRF responses have Cache-Control: no-store.

Every authenticated POST in this auth router requires X-CSRF-Token to match the
session nonce, compared using `hmac.compare_digest` after bounded ASCII-format
validation. Another session's nonce fails. GETs require no CSRF header. The eventual
React client obtains the nonce through credentialed GET, holds it in memory and
sends it as a header alongside credentialed POSTs. It never reads the session
credential itself. CORS allows credentials only for configured exact origins.

Additionally every unsafe /api/v1 request requires application/json and
X-PAWTEL-Request: 1. Any supplied Origin must be allowlisted. These non-simple
requests require browser preflight, preventing HTML forms from performing login or
registration CSRF before a session exists. Requests without Origin support explicit
CLI/API clients, but still require the custom header and JSON. CORS alone is not
used to prevent ordinary form submissions; the custom-header/content-type checks
are enforced on actual requests too.

CSRF exploits a browser automatically attaching someone else's authentication cookie
to an attacker-induced request. SameSite helps but is not the only boundary; same-site
origins and deployment mistakes can weaken it. CSRF does not protect against XSS:
malicious same-origin JavaScript can fetch the nonce and submit authenticated actions.

A future state-changing router must apply the CSRF dependency as this router does;
the custom header/Origin middleware by itself is not a replacement for it. Sensitive
future services must also recheck permissions/state inside their transaction.

## Endpoints and exact semantics

All POSTs require the custom header and JSON, including `{}` for logout. If the
request has a valid session, all POSTs also require its CSRF nonce, even login,
registration and email verification. Anonymous requests do not have a nonce.

| Endpoint | Success / purpose | Authentication and important failures |
|---|---|---|
| POST /api/v1/auth/register | 201: safe user plus verification_delivery=not_configured; no automatic login | Anonymous allowed. 422 invalid fields; 409 canonical email unavailable. |
| POST /api/v1/auth/login | 200: safe self representation; sets new session cookie | Anonymous allowed; generic 401 invalid credentials. Unverified active users can establish limited sessions. |
| GET /api/v1/auth/me | 200: id, email, display_name, email_verified_at, is_active, created_at | 401 absent/dead session; 403 inactive account. Unverified active users may read self. |
| GET /api/v1/auth/csrf | 200: csrf_token only | 401 absent/dead session. An inactive but authenticated user may obtain this nonce solely to log out safely. |
| POST /api/v1/auth/logout | 204: revoke current session and clear cookie | Valid session needs CSRF. No valid session, an expired/revoked cookie, or repeated logout returns 204 and clears the cookie, without revoking other devices. Request-header/Origin rules still apply. |
| POST /api/v1/auth/verify-email | 204: consume capability and mark its target email verified | Anonymous capability use allowed. Generic 400 for invalid, expired, consumed, changed-email or inactive-target token. Authenticated requests require CSRF. Malformed/oversized bodies can produce 422. |

Safe user responses use an explicit Pydantic whitelist, not ORM __dict__. No password
hash, session digest, verification digest or raw credential is included. Only the
CSRF nonce is intentionally readable through its dedicated endpoint. /health remains
unchanged and database-independent.

## Verification persistence and delivery boundary

Verification credentials also use independently random 256-bit tokens, with only
purpose-separated SHA-256 digests in the database. A row holds user_id, a snapshot
of the target email, created_at, expires_at and consumed_at. The default lifetime
is 24 hours. The token cannot verify a subsequently changed address.

The unique user_id allows only one latest row per User. Internal token replacement
locks and refreshes the User, rejects inactive/already-verified users, deletes the
previous row and inserts the replacement atomically. Older secrets immediately stop
working. This bounds row accumulation but does not retain token-issuance history.
There is no public resend endpoint or resend delivery claim. A future exposed resend
flow will also need throttling/cooldown and provider-failure handling.

RegistrationResult carries the raw token only in memory for a future delivery caller
or controlled tests, with repr disabled for that field. The current API discards it
and truthfully reports verification_delivery=not_configured. It does not log tokens,
return a development-only secret or pretend email was sent. A developer currently
exercises verification through integration tests/internal service helpers, not an
email inbox. A real adapter/reliable delivery or outbox policy is deferred; no
elaborate unused provider interface has been introduced.

## Transactions and authorisation dependencies

Registration hashes outside the transaction, then inserts User and verification
state within one explicit SQLAlchemy begin block. Any token-creation failure rolls
back the inserted User. Unique-email errors become a safe conflict, not raw SQL.

Login reads the candidate, verifies its hash without holding a row lock, then locks
and refreshes User, rechecks active state/hash, optionally rehashes, revokes the
current browser session and inserts its replacement in one transaction. The cookie
is set only after commit. Logout atomically updates only the current session.

Verification looks up the digest, locks User first and then refreshes/locks the token,
checks current expiry/address/consumption state, and updates both consumed_at and
email_verified_at in one transaction. Issuance/replacement uses that same User lock
order. Two consumers cannot both accept a token, and a token replaced while another
request waits is rechecked rather than trusted from a stale read. Tests cover
sequential replay and rollback after an actual token UPDATE; this is not a claim
of a complete concurrent stress test.

Reusable dependencies distinguish identity (required_user), active account
(active_user) and verified email (verified_user, which also requires active). The
optional context is genuinely used for idempotent logout and conditional CSRF.
There are no invented roles, admin checks or host permissions. Frontend visibility
will never replace backend checks. Dependencies provide request-time checks, not a
lock held across a future marketplace transaction; sensitive services must recheck
relevant business state in their own transaction.

## Errors and logging

Application errors have a stable envelope:

```json
{"error":{"code":"invalid_credentials","message":"Email or password is incorrect."}}
```

Important codes: invalid_credentials (401), authentication_required (401),
account_inactive (403), email_not_verified (403), csrf_failed (403),
untrusted_origin (403), request_header_required (403), json_required (415),
validation_error (422), registration_unavailable (409), verification_invalid (400),
internal_error (500), and http_error for safe framework errors such as 404.
CORS preflight negotiation remains handled by the framework.

Validation errors never echo Pydantic input/body/context. SQLAlchemy errors are
handled without logging the exception: PostgreSQL DETAIL can contain whole rows,
even when SQL parameters are hidden. Unexpected failures return the same safe 500;
logging records only the exception class, not its text, traceback, request body or
credentials. This favours redaction over detailed diagnostics; richer production
observability needs a carefully reviewed sanitisation policy. Never enable verbose
body/cookie/SQL logging around these routes. Synthetic tests verify error/log redaction.

## Local exercise (no credentials printed)

Apply migrations, start Uvicorn using README instructions, and use the explicit local
HTTP .env settings. From backend with the virtual environment active, the following
uses a hidden terminal password prompt and keeps cookies only in HTTPX memory:

```zsh
python - <<'PY'
from getpass import getpass
import httpx

email = "developer@example.com"  # Change to your local demo identity.
password = getpass("Passphrase (15-128 characters; not printed): ")
headers = {"X-PAWTEL-Request": "1", "Origin": "http://localhost:5173"}
with httpx.Client(base_url="http://localhost:8000", headers=headers) as client:
    registration = client.post("/api/v1/auth/register", json={
        "email": email, "display_name": "Developer", "password": password,
    })
    print("Registration status:", registration.status_code)
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    del password
    print("Login status:", login.status_code)
    if login.status_code != 200:
        raise SystemExit("Login failed; use the same credentials for an existing demo account.")
    print("Safe current user:", client.get("/api/v1/auth/me").json())
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    logout = client.post("/api/v1/auth/logout", json={}, headers={"X-CSRF-Token": csrf})
    print("Logout status:", logout.status_code)
    print("Current-user status after logout:", client.get("/api/v1/auth/me").status_code)
PY
```

This does not verify email or deliver anything. It creates a local demo account in
development intentionally; database integration tests instead use pawtel_test and
roll back their synthetic data. Never print client cookies, token values or password
hashes when debugging. The eventual React client uses credentials: include, the
same required headers and an in-memory nonce; no frontend auth UI was added here.

## Known limits before public deployment

Rate limiting/credential-stuffing controls, breached-password screening, request-size
limits at the deployment boundary, TLS/proxy hardening, XSS/CSP work, email delivery,
password reset, MFA/OAuth, expiry cleanup jobs, logout-all-devices and complete audit
history are deferred. Ordinary revocation only affects subsequent requests; it
cannot recall an already-authorised in-flight response. The sessions table needs
expiry/revocation retention cleanup before long-running public use. There is no
claim of timing immunity, distributed authentication scalability or complete security.

References: [Argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html),
[RFC 9106](https://www.rfc-editor.org/rfc/rfc9106.html),
[OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## Pet resource extension (Milestone 4)

The Pet router reuses active_user and csrf_for_authenticated_requests for POST,
PATCH and DELETE, permitting private profile preparation before email verification.
CORS now permits PATCH/DELETE as well as GET/POST for exact configured origins.
JSON/custom-header/Origin rules also apply to DELETE (send `{}`). All /api/v1
responses, including private Pet reads, now use no-store headers. No auth policy,
password/session format or frontend feature was changed. See [Pet Profiles](pet-profiles.md).

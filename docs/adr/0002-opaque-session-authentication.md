# ADR 0002: PostgreSQL-backed opaque session authentication

Status: accepted for Milestone 3.

## Context

PAWTEL is a browser-oriented marketplace with an existing relational database. It
needs understandable revocation, account-state checks and credential protection,
without a second session store or premature distributed infrastructure. Authentication
must not imply that marketplace authorisation or email delivery already works.

## Decision

Use Argon2id through argon2-cffi for passwords (explicit RFC 9106 low-memory profile)
and a 15–128-character passphrase-friendly registration policy. Preserve existing
User identity and canonical email rules. A nullable password column keeps old domain
rows usable without inventing credentials; only registration creates password users.

Generate independent opaque 256-bit session and verification tokens with secrets.
Store only purpose-separated SHA-256 digests for those high-entropy credentials.
Use PostgreSQL session rows with fixed expiry/revocation, an HttpOnly host-only
SameSite=Lax cookie, and Secure/__Host- defaults. Local HTTP requires an explicit
non-production opt-in. One browser can revoke/rotate its session without logging
out other devices; no JWT or Redis is introduced.

Use a synchronizer CSRF nonce stored on each session and returned by authenticated
GET. Require it on authenticated auth POSTs, plus exact Origin checks, a custom
request header and JSON-only unsafe requests to cover pre-session login/registration
CSRF. SameSite and CORS are additional boundaries, not a substitute for these checks.

Verification records have a target-email snapshot and one latest row per user.
Replacement and consumption lock User and run transactionally. The raw delivery
token is an internal ephemeral result, never an API response. No provider/resend
endpoint is fabricated. Stable safe errors and explicit output schemas protect
against credential disclosure; login uses generic failures and dummy verification.

## Alternatives considered

JWT access/refresh tokens would add rotation/revocation decisions without removing
this application's need for database checks. Client-storage bearer tokens expose a
readable credential to JavaScript. A separate Redis store adds infrastructure before
there is a measured need. Database-raw session credentials would be directly replayable
after database disclosure. Fast hashes for passwords would not slow guessing.
Double-submit CSRF is valid, but the existing session row makes a stable synchronizer
nonce simple, without another browser cookie or a signing-key lifecycle.

## Consequences and trade-offs

Each authenticated request depends on PostgreSQL. The CSRF nonce is readable but
cannot authenticate alone; XSS can still act as the user. Immediate revocation means
subsequent lookups fail, not that in-flight work can be recalled. Argon2 needs memory/
load benchmarking and abuse controls before public deployment. Duplicate-registration
conflicts still expose existence; dummy login work is risk reduction, not timing
immunity. Email delivery/recovery, throttling, cleanup and deployment hardening remain
explicit later work. A read-only database theft still exposes PII/password hashes
and CSRF nonces, even though it does not reveal replayable session/verification tokens.

See [authentication details](../authentication.md) and [interview notes](../authentication-interview.md).

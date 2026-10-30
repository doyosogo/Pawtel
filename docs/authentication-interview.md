# Authentication interview notes

Authentication answers who is making a request. Authorisation answers whether that
identity may perform this action. PAWTEL can establish an unverified user's session
and return their own profile, while a verified-user dependency denies future
marketplace actions until email verification. This is backend enforcement; hiding
buttons in React cannot enforce it.

Passwords are hashed, not encrypted: the server verifies a candidate without needing
to recover the original. Argon2id deliberately spends memory and CPU, using a random
salt, to raise offline guessing cost. SHA-256 is appropriate for random 256-bit tokens
but too fast for ordinary human passwords.

The browser holds an opaque HttpOnly cookie. The database holds only its digest and
session state. A read-only database leak does not immediately provide replayable
session tokens, although it still exposes PII and password hashes. Server-side rows
make revocation straightforward, at the cost of a database lookup. JWTs would add
revocation/refresh complexity without a demonstrated benefit for this application.

HttpOnly blocks JavaScript from reading a cookie. Secure restricts it to HTTPS.
SameSite=Lax reduces when cookies accompany cross-site requests. None fixes XSS.
Because browsers attach cookies automatically, PAWTEL requires an independent,
unpredictable, session-bound CSRF header on authenticated POSTs. A malicious site
cannot read the synchronizer nonce through normal browser origin protections; an
XSS payload on the trusted site can, so CSRF is not an XSS defence.

Registration inserts the user/hash and verification state together or rolls both
back. Verification locks and rechecks the user/token and writes consumption and
verification together. No external email call is performed under those locks.
Dummy Argon2 verification and generic login errors reduce obvious enumeration
signals, but do not establish mathematical timing equivalence.

## Questions and model answers

1. **Why opaque sessions rather than JWTs?** PostgreSQL already exists, and request-time
   state makes logout and disabled-account checks simple. The trade-off is database
   availability/lookup cost instead of a token revocation and refresh scheme.
2. **Why not use SHA-256 for passwords too?** Passwords are guessable; Argon2id makes
   each guess costly. Session tokens have 256 bits of randomness, making fast digest
   lookup appropriate without treating them as human passwords.
3. **Can a stolen database authenticate directly as users?** It cannot directly replay
   the stored token digests as cookies. It still exposes sensitive data and hashes
   that permit offline password guessing; this is damage reduction, not immunity.
4. **What does logout do with two devices logged in?** It timestamps revocation of
   only the current session, then clears that cookie. The other session still works.
5. **Why is SameSite not enough?** It is useful defence in depth, but same-site origins
   and deployment assumptions can weaken it. A session-bound nonce and explicit
   request checks provide an independent action authorisation signal.
6. **How does the future React app obtain CSRF protection?** Credentialed GET /csrf
   returns a nonce. React keeps it in memory and sends X-CSRF-Token on POSTs, with
   credentials: include, JSON and X-PAWTEL-Request: 1. It never reads the session cookie.
7. **What if token creation fails after inserting a user?** The registration service's
   transaction rolls back the user insert. A deliberate failure integration test
   proves that partial registration is not left behind.
8. **What prevents verification-token replay?** Expiry/consumption checks and a User
   row lock followed by a refreshed token read. The successful transaction consumes
   the token and verifies its email atomically; subsequent use is a generic failure.
9. **What if the email changes before verification?** The token stores its target
   address. A mismatch with the current User email is rejected rather than verifying
   an address the original token never proved.
10. **Is login timing-attack proof?** No. Unknown emails use dummy Argon2 work and the
    same generic error, reducing a trivial discrepancy; scheduling, caches and other
    effects still differ. Rate limiting and monitoring are also needed.
11. **What is still missing before public launch?** Real email delivery/recovery,
    throttling, credential-stuffing controls, deployment/TLS/body-size hardening,
    cleanup/retention, and the later transactional marketplace permissions/workflows.

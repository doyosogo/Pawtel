# Private Pet Profiles — Milestone 4

This milestone exposes the existing Pet model as the first authenticated business
resource. It adds no columns, enum values, indexes or migration. Pet fields remain:
UUID id/owner_id, name (80), DOG/CAT species, optional breed (100), optional date of
birth, is_active and timezone-aware created_at/updated_at.

No pet screen/form, image storage, medical/vet/temperament/vaccination data, listings,
host onboarding or booking/payment workflow is implemented.

## Authentication and authorisation

All five endpoints require the existing authenticated **active** User dependency.
Email verification is deliberately **not** required for profile preparation: an
unverified active user can create, view, correct and archive their own pets.
Marketplace participation such as requesting/accepting bookings will require verified
email later. No arbitrary roles, host permissions or new authentication logic exist.

Authentication identifies the User behind the session cookie. Authorisation limits
which Pet rows that User may access. A UUID is an identifier, not an access grant.
The route derives owner_id only from the authenticated User; request schemas forbid
owner_id, even when the supplied ID is the caller's own. A client cannot choose or
transfer ownership. The API never accepts id, timestamps or is_active as writable
profile properties either.

Every resource read uses both Pet.id and Pet.owner_id in SQL. PATCH/DELETE also put
both predicates in the **actual UPDATE**, instead of doing an unscoped write after
a separate Python ownership check. The list query filters owner and active state
in PostgreSQL; it does not fetch all users' pets and filter them in Python.

### Private not-found policy

A valid UUID that does not exist and a Pet belonging to another user both return:

```json
{"error":{"code":"pet_not_found","message":"Pet not found."}}
```

Both are HTTP 404 for GET, PATCH and DELETE. There is no not_owner error or global
lookup that exposes the other record first. This reduces unnecessary resource
existence disclosure; it is not a complete privacy or timing defence. UUIDs, cookie
security, backend authorisation, future abuse controls and careful logging all
still matter. A malformed UUID is a separate input error: 422 validation_error.

## API contract

| Endpoint | Result |
|---|---|
| POST /api/v1/pets | 201 with the created owner Pet; owner is assigned by the server. |
| GET /api/v1/pets | 200 array of the caller's active pets. |
| GET /api/v1/pets?include_archived=true | 200 array of all the caller's pets, including archived ones. |
| GET /api/v1/pets/{pet_id} | 200 owner Pet, including an archived Pet; otherwise private 404. |
| PATCH /api/v1/pets/{pet_id} | 200 updated owner Pet; only supplied editable fields change. |
| DELETE /api/v1/pets/{pet_id} | 204 soft archive; no database row is deleted. |

Collections sort by created_at ascending, then UUID ascending as a stable tie-breaker.
There is no pagination or hard pet-count cap in this version: a normal household's
pet collection is expected to be small. Revisit pagination/limits if actual usage
or abuse demands it, rather than introducing a generic pagination framework now.
There are no measured throughput or index-performance claims.

Responses use an explicit PetOutput whitelist: id, name, species, breed,
date_of_birth, is_active, created_at and updated_at. Neither owner_id nor any User
relationship is serialized. Password hashes, session data and verification state
are outside this response boundary. All /api/v1 responses now use no-store cache
headers so private collections are not shared or retained as a cacheable resource.

## Validation and PATCH semantics

- Name is required on creation, trimmed and limited to 1–80 characters after trimming.
  Blank/whitespace-only names are rejected.
- Species is exactly DOG or CAT. Lowercase/unknown strings are not silently coerced.
- Breed is optional, trimmed and limited to 100 characters after trimming. Empty or
  whitespace-only strings become null.
- Date of birth is optional, supplied as a real YYYY-MM-DD calendar date or null.
  Timestamps/datetime strings are rejected, as are impossible dates and dates after
  the current **UTC calendar day**. There is no arbitrary maximum-age rule.
- Unknown fields are forbidden. Immutable identity/ownership/timestamp fields and
  archive state cannot be changed by either create or PATCH payloads.
- An empty PATCH object returns 422. Omitted fields remain unchanged. Explicit null
  clears breed/date_of_birth, but null name/species is rejected.
- A nonempty PATCH repeating an existing valid value returns 200 as a valid update;
  it executes an UPDATE, with updated_at maintained by the existing SQLAlchemy rule.
  Timestamps are informational, not uniqueness or concurrency tokens.

Validation errors use the existing safe 422 envelope and never expose SQL detail.
Missing/dead authentication receives 401 authentication_required; an inactive account
receives 403 account_inactive. Existing request-metadata/CSRF errors may precede those
checks when the request itself is malformed or untrusted.

## Soft archive

DELETE changes is_active from true to false. The Pet UUID and profile remain in the
database so future BookingPet references can continue pointing to the same record.
Archiving does not claim that historical profile details have been snapshotted.

The owner can still GET the archived record and list it with include_archived=true.
Metadata corrections via PATCH remain allowed, but never set is_active back to true.
There is no restore endpoint. Repeated DELETE of an already archived own Pet returns
204 and performs no additional UPDATE; in that sequential case updated_at is unchanged.
Another user's archived Pet still returns the same private 404.

## CSRF, cookies and browser compatibility

The router reuses Milestone 3's active-user and synchronizer-CSRF dependencies. POST,
PATCH and DELETE need the session's X-CSRF-Token, JSON content type and
X-PAWTEL-Request: 1. A supplied Origin must be in the configured allowlist. DELETE
must send JSON `{}` to follow the existing request-protection contract. Safe GETs
need no CSRF header. Retrieve the nonce through GET /api/v1/auth/csrf and retain it
in memory; the session credential stays in its HttpOnly cookie.

The eventual React client uses credentials: include. Credentialed CORS now permits
PATCH and DELETE in addition to GET/POST for exact configured origins. No frontend
implementation or visual changes were needed. CSRF does not protect against XSS.

## Services, transactions and concurrency

Routes validate/serialize HTTP data and pass owner.id to focused pet service
functions. Services own explicit SQLAlchemy begin/commit/rollback boundaries, as
in the existing authentication services. Creation flushes the new row inside its
transaction; PATCH uses owner-scoped UPDATE ... RETURNING; archive uses a conditional
owner-scoped UPDATE, with an owner-scoped existence check for the already-archived
case. Helpers do not perform unrelated intermediate commits.

Only explicitly supplied PATCH properties are written. This avoids overwriting
omitted columns with stale values. It does **not** prevent lost updates to the same
field: the last successful database writer wins. Ordinary PostgreSQL UPDATE locking
still applies, but no explicit SELECT FOR UPDATE, version counter, ETag, If-Match
precondition or optimistic concurrency guarantee has been introduced. A future
version/updated_at precondition could be evaluated with a deliberate API contract;
current timestamps alone do not provide that protection. PATCH cannot race an
archive into reactivation because archive state is never part of the PATCH payload.

Authentication/account-state checks are request-time checks, as in Milestone 3;
this does not recall already-authorised in-flight operations after a concurrent
session revocation/account change. Future sensitive marketplace services need their
own transactional business checks.

## Database boundary and indexes

The Pet.owner_id foreign key proves that an owner User exists. It cannot identify
which HTTP caller authenticated through an opaque cookie. All application users
share the backend's database role; PostgreSQL has no implicit HTTP identity context.
A valid foreign key to User B would not make User A's request authorised. That is
why deriving identity on the server and scoping every query are separate requirements.

The existing ix_pets_owner_id supports owner collection/FK access patterns. The UUID
primary key supports identity lookup, with owner additionally constrained. No redundant
index is added for the small expected owner collection and its ordering; actual
planner choices depend on data and should be measured before tuning.

PostgreSQL RLS is not added. This application-owned database access model currently
has one trusted API boundary with explicit, tested owner queries. RLS would require
an additional role/policy/request-identity and connection-pool discipline. It may
be useful later if access patterns or isolation requirements change; it is not a
substitute for understanding the current application authorisation rule.

## Tests and deferred work

Integration tests use at least two real registered/logged-in users and the existing
protected pawtel_test database. They exercise missing authentication, both owners,
foreign/nonexistent equivalence, immutable fields, validation, sparse/null PATCH,
active/unverified policy, archive retention/idempotence, cross-session CSRF and
browser preflight. Deliberate failures after INSERT/UPDATE verify transaction rollback.
The shared HTTPX fixture is reused by the unchanged authentication behaviours.

No schema/index change or migration was needed. Committed migrations and the Pet
model remain unchanged. Pet images, health/medical information, booking-specific host
review access, restore, hard-delete/retention policy, pagination/limits and conflict
prevention remain future decisions. The current owner endpoint must not be weakened
later just to grant a host generic access to all Pet profiles.

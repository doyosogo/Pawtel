# ADR 0003: Owner-scoped private Pet Profiles

Status: accepted for Milestone 4.

## Context

Pet Profiles are PAWTEL's first private business API. Existing database ownership
foreign keys do not authorise the HTTP caller. UUID identifiers may be obtained by
another user, and valid sessions alone must not grant access to private profiles.
The committed Pet schema already supports the required profile fields and archiving.

## Decision

Derive owner_id only from the existing authenticated active User dependency. Permit
profile preparation before email verification, while retaining verified-user checks
for later marketplace participation. Use owner_id predicates in every resource
read and actual update/archive SQL statement. Reject client ownership/identity/
timestamp/archive fields. Serialize only an explicit Pet response whitelist.

Return the same 404 pet_not_found for another owner's Pet and a nonexistent valid
UUID. DELETE soft-archives; it preserves the UUID/row for future references, and
repeated owner archive is idempotent. Archived metadata remains owner-editable,
but no restore API exists. Reuse the current schema/index and authentication/CSRF
protections; create no new migration, generic repository layer or explicit row locks.

## Alternatives considered

- Global fetch followed by an owner check: easy to misuse or disclose a record first;
  owner-scoped SQL makes the boundary explicit at every data access.
- Client-provided owner_id: trusts an attacker-controlled relationship selector.
- A distinct not_owner/403 response: unnecessarily confirms private resource existence.
- Hard deletion: loses the stable record required by future booking references.
- PostgreSQL RLS now: adds policy/role/request-context and pooling responsibilities
  to a single trusted API access model without a current requirement for that layer.

## Consequences and trade-offs

Application code is the authorisation authority; foreign keys remain the referential
integrity authority. Every future private Pet access path must preserve this rule
or introduce a separately justified permission model. A uniform 404 reduces one
form of enumeration but is not a complete privacy defence. Same-field concurrent
PATCH remains last-writer-wins; omitted fields are preserved, not version-protected.
Unpaginated collections fit expected household usage but do not enforce a count cap.

See [Pet API and ownership](../pet-profiles.md) for exact semantics and limitations.

# Private Host and Listing management

Milestone 5 adds private management, not public marketplace browsing. One User can
own pets and optionally enable Host mode. HostProfile uses user_id as its shared
primary/foreign key; it is not a second account, role or login.

## Authentication and API contract

Every endpoint below requires the existing authenticated, active, verified-user
dependency, including reads. Pet setup remains available before verification;
hosting introduces marketplace configuration and requires verified email. This is
a consistent private management gate, not proof of host identity/suitability.
Missing session: 401 authentication_required; inactive: 403 account_inactive;
unverified: 403 email_not_verified. Unsafe methods also require JSON,
X-PAWTEL-Request: 1, a valid session X-CSRF-Token and an allowed Origin when supplied.
GET needs no CSRF nonce. Responses use explicit schemas and Cache-Control: no-store.

All paths are relative to `/api/v1/host`:

| Method/path | Contract |
| --- | --- |
| GET /profile | 200 own profile; 404 host_profile_not_found if not enabled |
| POST /profile | 201 creates own profile; optional bio; repeated creation is 409 host_profile_exists and never overwrites data |
| PATCH /profile | 200 edits bio only; missing profile is 404 |
| POST /listings | 201 creates own DRAFT; requires HostProfile or 403 host_profile_required |
| GET /listings | 200 own non-archived records; optional ?status=DRAFT, PUBLISHED or ARCHIVED |
| GET /listings/{id} | 200 owned record, including archived records |
| PATCH /listings/{id} | 200 partial configuration/lifecycle update |
| DELETE /listings/{id} | 204 soft archive; repeat 204; send an empty JSON object |

Listing operations require HostProfile. Direct foreign/missing valid UUIDs produce
identical 404 listing_not_found once that prerequisite is met. Malformed UUIDs and
invalid request fields return 422 validation_error using the existing safe error
envelope. Archived PATCH returns 409 listing_archived for its owner. No endpoint
accepts user_id, host_id, owner_id, IDs or timestamps in request JSON. Unknown fields
are forbidden. Responses never traverse User/authentication relationships.

## Validation and lifecycle

POST requires title, description, suburb, state, postcode, max_pet_capacity,
base_nightly_price_cents and additional_pet_price_cents. country_code defaults to AU
and only AU is valid. accepted_species defaults to an empty list. For example:

```json
{"title":"Boarding accommodation","description":"Private listing configuration",
 "suburb":"Norwood","state":"SA","postcode":"5067","max_pet_capacity":3,
 "base_nightly_price_cents":6500,"additional_pet_price_cents":1500,
 "accepted_species":["DOG","CAT"]}
```

Text is trimmed: title 1–160, description 1–10000 and suburb 1–100 characters. Bio
is optional, at most 2000 characters; null/blank clears it. Postcodes are four ASCII
digits stored as strings so leading zeros survive. State uses the existing Australian
enum. These are structured input checks, not verification of suburb/postcode matches
or geocoded truth. No location provider is called.

Capacity is a strict integer 1–2147483647, matching PostgreSQL INTEGER storage.
Prices are strict integers 0–9007199254740991 cents: booleans, floats and numeric
strings are rejected. The upper bound preserves exact JSON integers for eventual
JavaScript consumers and fits BIGINT; it is not a recommended business price.
Hosts configure prices; the future server booking service calculates authoritative
quotes, rounding and the 10% service fee. Capacity configuration does not establish
availability on any date.

Only DOG/CAT are supported; duplicate entries are rejected, not silently discarded.
The relational composite primary key remains the final duplicate boundary. Species
responses are sorted deterministically. Drafts can have no species while being
prepared; PUBLISHED requires at least one. Other required fields still apply to drafts.
Creation cannot specify status and always starts DRAFT. PATCH permits DRAFT ↔ PUBLISHED,
including staying in the same state. DELETE moves either to ARCHIVED and preserves
Listing/species rows. Archives are readable by the owner but cannot be edited or
restored. No Host removal, listing hard-delete, moderation or booking-dependent
transition is implemented. PUBLISHED has no public endpoint in this milestone.

PATCH rejects empty bodies, explicit null Listing fields, immutable fields and
unsupported statuses. Omitted fields remain unchanged. A supplied identical value is
accepted; it may advance updated_at. Collections sort by created_at then UUID, with
no pagination because expected per-host counts are small; revisit if usage warrants.

## Ownership, transactions and database boundary

Routes are thin; focused Host/Listing services own explicit db.begin transactions.
User identity comes exclusively from authentication. HostProfile resolution uses
that User's shared key. Resource SELECT/UPDATE statements include both Listing ID
and that Host key. Collection filtering happens in SQL, not after loading all rows.
Foreign and missing private IDs share 404 to avoid unnecessary existence disclosure;
UUID unpredictability complements, never replaces, authorisation.

Creation inserts the Listing and species associations atomically. Updates write the
owned parent before replacing species and validating the final publish configuration.
The ordinary UPDATE's inherent PostgreSQL row-write lock remains held until commit,
so related species changes through this service serialize on the same parent. No
explicit booking-style SELECT FOR UPDATE or distributed lock was added. Relationship
replacement and field changes roll back together, including injected post-flush failures.
Reads join parent/species in one SQL statement for a consistent statement snapshot.

This is not optimistic concurrency control: conflicting edits to the same field
remain last-successful-writer-wins. No ETag/version check detects stale clients.
Future booking/capacity writers need their own coordinated transaction protocol.

PostgreSQL enforces valid FKs, one HostProfile per User, positive capacity, nonnegative
prices, country/postcode/state constraints and unique listing/species pairs. It does
not identify the HTTP caller, enforce verified email, or require a species before
publication. Those contextual rules belong to the authenticated services. Direct SQL
writers must respect that boundary; PostgreSQL RLS/triggers are not introduced.

No migration was needed. Existing HostProfile and Listing primary keys support
identity lookups; ix_listings_host_id supports host collection filtering. Listing
identity queries also include host ownership. The species composite PK begins with
listing_id. No redundant indexes or measured performance claims were added.

## Tests and limitations

Real protected PostgreSQL tests use multiple independently authenticated users,
exercise foreign/missing UUID equivalence, spoofed identity rejection, active/verified
gates, CSRF, strict validation, species replacement, lifecycle preservation and
creation/update rollback after injected association-write failures. Existing auth,
Pet and migration tests remain part of the full suite.

No Host frontend, public search/listing detail, images, maps, external email delivery,
bookings, availability, pricing calculation or payments exists. Verification tokens
are exercised internally by tests; production endpoints do not expose them. Existing
auth deployment/rate-limiting limitations still apply.

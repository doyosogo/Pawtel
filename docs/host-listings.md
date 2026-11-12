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

## Milestone 6 follow-up

Public PUBLISHED discovery/detail and advisory availability now exist through the
separate [public API](listing-discovery.md). The private contracts above, including
verified-user management gates, remain unchanged. Booking workflows and Host UI
are still deferred.

## Milestone 7 capacity protection

Once bookings reserve capacity, a capacity edit below the existing reserved peak
returns 409 listing_capacity_reserved and rolls back the full Listing update. The
existing parent UPDATE coordinates with Booking acceptance's Listing lock. Archive
preserves reservations but blocks new requests/acceptance; Owner cancellation still
releases them. See [Booking protocol](bookings.md).

## Host website and Listing media (Milestone 12)

Verified authenticated Users without HostProfile can open `/host` and choose
**Become a Host**, with an optional bio. This uses the existing profile POST; bio
editing uses PATCH. Owner and Host remain one User account. Unverified Users get
truthful no-email-delivery guidance; there is no verification bypass.

`/host` provides profile editing, Listing counts, recent pending-request summary,
Booking inbox navigation and Create Listing. `/host/listings` shows owned active
Listings by default; DRAFT/PUBLISHED/ARCHIVED filters use the existing API. Create
at `/host/listings/new`; edit at `/host/listings/:id/edit`. Only changed fields are
patched. Archived Listings are read-only and preserved for Booking history.

Forms contain title/description, structured Australian suburb/state/postcode,
capacity, base/additional-pet nightly AUD prices and DOG/CAT accepted-species
checkboxes. Currency is parsed from decimal strings through integer/BigInt cents,
not floating-point multiplication. Negative/malformed/more-than-two-decimal prices
are rejected. Base price covers the first Pet; extra price applies per additional
Pet per night. Hosts do not configure the 10% service fee. Capacity is Pets staying
at the same time, not a Booking count; existing reservation floors still apply.
Postcode/suburb combinations are not geographically validated. There are no maps.

New Listings are DRAFT and hidden from guests. Empty accepted species is permitted
in drafts, but publication requires at least one. Explicit Publish listing, Move
to draft and confirmed Archive listing actions map to existing PATCH/DELETE rules.
No Host IDs, User IDs, timestamps or arbitrary lifecycle metadata are submitted.

### Image configuration, limits and endpoints

Cloudinary is the sole selected media provider. Install backend dependencies from
pyproject.toml; Cloudinary SDK and Pillow are new dependencies. Configure the
following privately in ignored root `.env`, using an isolated development product
environment. Never prefix these with VITE_ or commit their values:

- CLOUDINARY_CLOUD_NAME
- CLOUDINARY_API_KEY
- CLOUDINARY_API_SECRET

No unsigned browser preset, master credential in React, custom image server or
new frontend SDK is needed. Cloud name appears in intended public delivery URLs;
server API credentials do not. Empty .env.example values do not enable uploads.
Save the draft first, then upload photos in its editor. Lack of provider setup does
not prevent profile/Listing editing, publication or deterministic demo imagery.

Apply the new additive migration before starting the updated backend:

```zsh
# From repository root
cd backend
source .venv/bin/activate
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Image API, all behind existing verified active User/Host ownership and CSRF rules:

- POST `/api/v1/host/listings/{id}/images?alt_text=...`: binary File body with its
  image Content-Type, X-PAWTEL-Request and X-CSRF-Token. Returns safe metadata (201).
- PATCH `/api/v1/host/listings/{id}/images/order`: JSON image_ids containing exactly
  the current READY set in desired order. Stale/foreign/duplicate IDs are rejected.
- DELETE `/api/v1/host/listings/{id}/images/{imageId}`: hides the association and
  returns cleanup_pending so failed provider deletion is visible.

Private/public Listing DTOs now include ordered `images`: id, HTTPS delivery URL,
alt text and sort order only. UPLOADING/DELETE_PENDING and provider IDs/credentials
are not public fields. Images are eager-loaded with Listings to avoid N+1 queries.

Limits: six images per Listing including pending intents; 5 MiB incoming and
re-encoded size; JPEG/PNG/WebP; one frame only; 200–6000 pixels on each side and at
most 24 megapixels. MIME must match decoded format. Pillow validates actual bytes,
loads/normalizes pixels, applies EXIF orientation and re-encodes without original
metadata/trailing content. Filenames, client URLs and claimed Host identity are
not trusted. React performs preliminary type/size checks, but the backend decides.

The editor offers a selected-file preview, uploaded thumbnails, optional alt text,
explicit move-earlier/later controls and remove. First READY photo is the cover.
Public cards use the uploaded cover; detail displays a responsive ordered gallery.
Missing or failed image delivery falls back to labelled original demo illustrations.
Existing fictional seeds create no media rows and need no external uploads.

### Failure recovery and operations

UPLOADING is committed before the provider call; READY is committed only after
provider success and rechecking ownership/archive state. Pending slots serialize
on the Listing row to enforce six under competing uploads. Provider calls occur
outside transactions. Provider failures may have an uncertain remote outcome and
retain the intent for later cleanup. DB association failure attempts compensating
deletion; if that fails or the process crashes, the intent remains recoverable.
The API returns a safe error asking the Host to refresh before retrying.

Deletion hides the photo in the DB before requesting provider deletion. If provider
deletion fails, cleanup_pending is true and DELETE_PENDING remains. Run in a
configured backend environment:

```zsh
python -m app.media.cleanup
```

The command processes at most 100 tracked delete intents or abandoned uploads
older than 15 minutes, ordered oldest first, and never targets READY images. It
prints counts only. Repeat as necessary and schedule/monitor it before production.
If a DB commit outcome is uncertain, cleanup rechecks current state and preserves
READY associations. This is not a distributed transaction. Lost DB records or an
exceptionally late provider write require manual inventory reconciliation under
`pawtel/listings/` rather than broad deletion of unrelated provider assets.

Removing an image requests Cloudinary CDN invalidation; propagation is eventual.
Archiving a Listing hides it from PAWTEL public APIs but preserves its READY photos
for history; it does not promise that previously public URLs become private.
Photos must not contain sensitive personal data. Use provider quotas and separate
development/production environments; moderation, rate limiting and operational
monitoring remain production work. See [ADR 0008](adr/0008-cloudinary-listing-media.md).

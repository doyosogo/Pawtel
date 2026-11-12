# ADR 0008: Cloudinary Listing media with tracked upload intents

Status: accepted for the portfolio MVP.

Use the official Cloudinary Python SDK for server-mediated upload and delivery of
Listing photos. Cloudinary combines an upload API, image delivery and supported
format/quality transformations without operating an object-storage/CDN pipeline.
This is proportionate for six photos per Listing. S3-compatible storage was the
main alternative: portable object storage and more deployment control, but it also
requires image processing/delivery configuration. Direct unsigned browser upload
was rejected because it weakens upload control; signed direct upload could reduce
backend bandwidth later, but requires a trustworthy final association workflow.

PostgreSQL stores a ListingImage row with UUID, owning Listing FK, provider public
ID, generated HTTPS delivery URL, order, alt text, creation time and lifecycle
state. It does not store image bytes or provider credentials. Public serializers
allow only READY images with id/url/alt_text/sort_order; parent Listing visibility
rules stay unchanged. First ordered READY image is the cover. Demo seed Listings
remain usable without Cloudinary through deterministic labelled SVG placeholders.

Credentials stay in backend environment configuration. Verified active session
identity and Host ownership authorize every operation. No client-supplied Host ID,
remote upload URL, delivery URL or provider public ID is accepted. The backend
checks bytes with Pillow and strips metadata before upload. Only the exact binary
upload route relaxes JSON content-type enforcement; CSRF, request-header and origin
checks remain mandatory. Six slots include unfinished cleanup rows to bound abuse.

PostgreSQL and Cloudinary cannot share a transaction. A short Listing-locked
transaction reserves UPLOADING before any provider call. Another short transaction
marks READY after upload and another ownership/archive check. No provider network
call holds an inventory/database lock. Ambiguous provider failures retain the
intent; association failures attempt compensation. DELETE_PENDING immediately
removes a photo from public responses and retains identity until provider deletion
succeeds. `python -m app.media.cleanup` retries deleted assets and UPLOADING intents
older than 15 minutes, up to 100 per run. READY assets are never cleanup targets.
The grace period exceeds the SDK's bounded provider-call timeout. This is recovery,
not exactly-once distributed execution. A lost database or an unusually late remote
write still requires provider-prefix inventory reconciliation. Provider SDK errors
and credentials are never echoed in API responses or cleanup command failures.

Trade-offs: backend bandwidth/decoding load, provider dependency and quota costs,
manual/scheduled cleanup, and eventual CDN invalidation. Uploaded photos are public
CDN assets, including unpredictable draft URLs if a Host shares them. Draft/archive
visibility in PAWTEL is not private media access control or a CDN recall guarantee.
Production needs scheduled cleanup/monitoring, upload rate/concurrency limits,
quotas, backup/recovery and moderation/abuse controls before wider use.

Official references:
- [Python upload](https://cloudinary.com/documentation/django_image_and_video_upload)
- [Upload API](https://cloudinary.com/documentation/image_upload_api_reference)
- [Asset deletion and CDN invalidation](https://cloudinary.com/documentation/delete_assets)

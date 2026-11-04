# Stripe sandbox payments (Milestone 8)

PAWTEL uses the official Stripe Python SDK and Checkout Sessions, API version
2026-10-28.endive, ui_mode=elements, mode=payment, currency AUD, card-only. Checkout
manages card collection/authentication without PAWTEL implementing raw PaymentIntent
orchestration. Milestone 11 adds the React Checkout Elements website below. No PAN,
card details or saved-card credentials pass through PAWTEL. No live keys, Connect,
Host payouts, transfers, subscriptions or automatic refunds are supported.

## Configuration and local workflow

Configure ignored root .env (0600) with STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY,
STRIPE_WEBHOOK_SECRET and STRIPE_RETURN_URL. Empty example values intentionally do
not fabricate credentials. Only test-key prefixes are accepted, even in production
configuration. Secrets use Pydantic SecretStr. SDK payload logging is disabled;
application errors never echo provider exceptions. HTTPS is required for production
return URLs; URLs cannot contain userinfo, query or fragment. The return page reads backend Booking state and is never proof of payment.

Install the official CLI if needed:

```zsh
brew install stripe/stripe-cli/stripe
stripe sandbox create --email <email-you-explicitly-authorize>
# Or use stripe login and select a sandbox/test account.
```

Anonymous temporary sandboxes require an email, save keys in the CLI profile and
expire after seven days unless claimed. Never paste CLI credential output into
reports/source. Copy test keys privately into ignored .env; keep permissions 0600.
Do not transmit Git identity with --from-git without explicit permission.

From backend with the virtual environment active:

```zsh
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another local terminal:

```zsh
stripe listen --events checkout.session.completed,checkout.session.expired --forward-to localhost:8000/api/v1/webhooks/stripe
```

The listener displays a signing secret: place it privately in .env, restart FastAPI
and never commit/print it in reports. Use the matching sandbox for both API requests
and listener. Configure snapshot events at the integration's API version for a deployed
endpoint. Use Stripe's documented test cards only; never a real card. A CLI-generated
unrelated event is not sufficient to confirm a PAWTEL booking: provider IDs, metadata,
amount, currency and deadline must match a persisted attempt.

## Start Checkout and privacy

POST `/api/v1/bookings/{booking_id}/checkout-session`, JSON `{}`, requires authenticated,
active, verified Owner and existing CSRF/request/Origin protections. Booking must be
owned, AWAITING_PAYMENT and inside its payment deadline. Foreign/missing resources
share booking_not_found. Server fields/amount in the body are rejected. Amount comes
from accepted Booking snapshots, never current Listing prices or client input.
Two fixed quantity-one line items represent boarding subtotal and service fee.
Only booking_id/payment_attempt_id go into provider metadata; no email/Pet information.

Response includes payment_attempt_id, sensitive client_secret and expires_at. The
secret is returned only to that Owner, not saved, logged or put in a URL. Responses
remain no-store. Hosts receive no Stripe credentials through Booking DTOs. Frontend code keeps
client secrets only in component memory, outside caches and browser storage.

## Persistence and idempotency

PaymentAttempt belongs to one Booking (RESTRICT FK); multiple historical attempts
are possible. It snapshots amount/subtotal/fee/AUD, immutable create return URL and
absolute provider deadline; stores unique Checkout Session/PaymentIntent IDs when
known, timestamps, status and a safe reconciliation reason. No client_secret or raw
provider payload is a column. States:

| State | Meaning |
| --- | --- |
| CREATING | Local identity committed; provider outcome may be unknown |
| OPEN | Valid provider Session recorded and reusable |
| SUCCEEDED | Valid signed payment confirmed the Booking |
| EXPIRED | Provider Session expired unpaid |
| FAILED | Definite provider create rejection; a new attempt may be made within the same bounded window |
| CANCELLED | Cancelled Booking's provider Session is known expired/unusable |
| REQUIRES_RECONCILIATION | Paid/terminal mismatch, integrity issue or pending cancellation cleanup |

A partial unique index allows at most one CREATING/OPEN/REQUIRES_RECONCILIATION
attempt per Booking. Listing/Booking locks serialize normal creation; the index is
a durable backstop against another unresolved attempt. Session/PaymentIntent IDs
are unique. String CHECK states avoid introducing more native enum DDL for small
provider-specific state sets. Existing Booking enums/migrations remain untouched.

StripeWebhookEvent uses Stripe Event ID as primary key; stores type, object ID,
received/processed times and safe result. No body, signature or personal payment
payload is stored. Receipts intentionally have no attempt FK: unknown valid events
can be acknowledged without inventing a PAWTEL association. Object ID is indexed
for investigation. Expected amounts/currency and basic state/date rules use CHECKs.

## Provider/local transaction boundary and failure model

1. Short Listing-first/Booking-second transaction validates eligibility, creates or
   reuses the local attempt and commits before any Stripe call.
2. Gateway creates with deterministic key pawtel-checkout-{attempt_uuid}, or retrieves
   the existing Session. Parameters, including expiry/return URL, are persisted/fixed.
3. A second short transaction reloads Booking/attempt under locks and records IDs.

Timeouts/Stripe server errors/malformed replies leave outcome uncertain and preserve
the attempt/key. Retry replays the same identity. If Stripe succeeded but the second
DB write failed, retry recovers that same Session; there is no distributed transaction.
Concurrent starts use the same attempt/key. A definite create rejection marks FAILED;
a new identity can then be created without extending the window. Retrieval rejection
requires reconciliation rather than pretending no payment exists. Browser errors
use safe codes checkout_temporarily_unavailable, checkout_rejected, checkout_not_open,
payment_window_closed and payment_reconciliation_required; no provider internals.

OPEN Sessions are retrieved/reused; refresh does not create a new session. An expired
Session ends the Booking's payment window; the Owner needs a new booking request,
not an indefinitely renewed hold. Provider-paid reads do NOT confirm: they record
PAID_AWAITING_VERIFIED_WEBHOOK and wait for a valid success webhook. Old requests are
not retried after the bounded deadline, preventing reuse beyond Stripe's idempotency
retention. Stripe API v1 retains keys for at least 24 hours, not forever.

## Deadline policy

Host acceptance initially grants BOOKING_PAYMENT_WINDOW_SECONDS (default 30 minutes).
First Checkout replaces this with a fixed **61-minute** deadline from that start,
rounded to whole seconds. This extends the normal 30-minute window and provides
margin above Stripe's minimum 30-minute session expiration; it can shorten a custom
initial window longer than 61 minutes. This is an explicit MVP policy. New attempts
and refreshes retain the first Checkout deadline. New creates require at least 31
minutes remaining; unknown retries keep identical parameters. There is no unbounded
extension. Stripe requires expiration 30 minutes–24 hours after creation. Very slow
provider calls can exhaust the margin and fail safely; they do not silently extend.
Capacity stays reserved for the entire Session window and until explicit expiry.

## Signed webhook authority and duplicates

POST `/api/v1/webhooks/stripe` uses raw request bytes, Stripe-Signature and the official
Webhook.construct_event verifier (300-second tolerance). Body limit is 1 MiB. No JSON
re-serialization occurs before verification. Only this exact POST path bypasses
browser request-marker/Origin/CSRF checks; other application writes are unchanged.
Missing/invalid signatures fail 400 without DB mutation; test livemode must be false.

Supported snapshot events: checkout.session.completed and checkout.session.expired.
Unknown signed types, including individual card failures, are recorded IGNORED and
acknowledged. Card declines can be retried in an open Checkout; PAYMENT_FAILED is
not used by this card-only flow. Async payment methods/events are not enabled.
Zero-total Checkout may use no_payment_required, accepted only when expected amount
is zero. Stripe's other amount limits can still cause a definite create rejection.

Event ID INSERT ON CONFLICT is inside the same transaction as all related updates.
Concurrent duplicates wait on the unique key; a completed duplicate returns success
without repeating mutations. If processing fails, the receipt and Booking/attempt
changes roll back together so Stripe can retry. Valid-but-integrity-mismatched events
are recorded REJECTED/reconciliation rather than repeatedly applied. A 200 means the
verified event was handled, not that every event confirms a Booking.

Processing locks Listing, Booking then PaymentAttempt and refreshes ORM state from
the database. This matters when a webhook beats the create response: a cached CREATING
object must not overwrite a committed SUCCEEDED state. Only matching metadata,
Session/PaymentIntent identity, amount equal to both snapshots, AUD, exact deadline,
test payment mode and a completed paid Session can confirm AWAITING_PAYMENT.
No repricing or capacity reallocation occurs: CONFIRMED preserves the existing hold.
A delayed valid success may confirm an overdue but still-reserved AWAITING_PAYMENT
Booking. Received time/event timestamp is not used as an ordering assumption.

Expiry of a matching unpaid Session changes eligible AWAITING_PAYMENT to EXPIRED,
releasing capacity under Listing-first locking. Confirmed/SUCCEEDED states never
regress on stale expiry. Duplicate expiry is harmless. Paid/mismatched-money
reconciliation is sticky: a later stale expiry cannot erase money needing attention.

## Cancellation, late success and maintenance

Owner cancellation commits CANCELLED and marks active attempts
REQUIRES_RECONCILIATION/CANCEL_CLEANUP_PENDING under the existing inventory locks.
After commit, the gateway retrieves/recovers and expires the provider Session.
Cleanup failure leaves a durable pending condition; repeat cancellation/maintenance
can retry. No Stripe network call occurs while holding inventory locks. A cancellation
can race with provider payment: correctly signed late success leaves Booking CANCELLED
(or EXPIRED) and records PAID_BOOKING_NOT_PAYABLE with an observed completion timestamp.
It never silently resurrects or confirms an unreserved stay. Manual reconciliation/
refund in the Stripe sandbox is required; automatic refunds are not implemented.

Explicit local recovery (no scheduler/queue):

```zsh
python -m app.payments.maintenance --limit 100
# Optional targeted invocation:
python -m app.payments.maintenance --booking-id <booking-uuid>
```

Unstarted overdue holds with no unresolved attempt expire transactionally. Known
provider Sessions are retrieved/expired outside DB transactions, then reconciled
under Listing/Booking locks. Already-paid reads wait for signed webhook confirmation;
unknown outcomes remain UNRESOLVED and keep capacity conservatively. Inspect
PaymentAttempt reconciliation_reason and StripeWebhookEvent.object_id/results via
trusted local database tools and Stripe Dashboard/CLI. Do not directly edit Booking
states as a recovery shortcut. No maintenance action fabricates payment success.

## Real sandbox smoke command

After safe test keys are configured, run `python -m app.payments.smoke` from backend.
This explicit online check uses a transient synthetic Booking quote, creates/replays
a Checkout with fixed IDs/key, verifies test mode/AUD 11000 cents/metadata/expiry, then
expires the unpaid Session. It never charges a card, prints credentials or stores a
client secret. It does not claim to exercise a real paid card or full application
webhook journey. Ordinary pytest never invokes this command.

## Verification and remaining limits

Automated tests use the real protected PostgreSQL database, fake provider gateway,
real official-SDK raw-body signature verification and independent connections for
concurrent Event-ID duplicates. They require no Stripe network. Separate real sandbox
smoke verification must check test mode, expected AUD amount/metadata/expiry and
idempotent Session identity; it must never be fabricated if credentials are unavailable.

Synchronous webhook processing is short SQL work; no external calls under locks and
no queue/microservice. Introduce workers only if measured workload warrants them.
No live deployment readiness, refund automation, payouts/Connect, saved cards,
subscriptions, chargeback handling or guaranteed automated recovery is
claimed. Existing rate limiting, email delivery and deployment-hardening limits remain.

Official references: [Checkout create](https://docs.stripe.com/api/checkout/sessions/create),
[webhooks](https://docs.stripe.com/webhooks),
[idempotent requests](https://docs.stripe.com/api/idempotent_requests),
[temporary sandbox CLI](https://docs.stripe.com/cli/sandbox).

## Owner Checkout Elements website (Milestone 11)

The Owner Booking detail now links to `/account/bookings/:bookingId/pay` only for
AWAITING_PAYMENT. This route reads the Owner-only Booking API before showing any
checkout control, then rechecks status/deadline before Session creation and before
confirmation. These are UX checks; the backend still authorizes the request and
owns every transition. There are no Host payment controls or credentials.

The only added direct frontend dependencies are `@stripe/stripe-js` (10.2.1) and
`@stripe/react-stripe-js` (7.0.1). The `/checkout` React entry point provides
CheckoutElementsProvider, useCheckoutElements, ContactDetailsElement and
PaymentElement. Stripe.js loads from Stripe through the official pure loader only
when payment is opened. Stripe's controlled Elements collect contact/card data;
there are no PAWTEL card inputs. Supported Appearance API variables use PAWTEL's
palette and rounded corners. Stripe's current Checkout total is displayed and
checked against the saved AUD Booking total before confirmation.

One compatibility correction was required for the existing 2026-10-28.endive API
pin: Checkout creation now uses `allowed_payment_method_types: ["card"]` instead
of the removed `payment_method_types` input. `ui_mode="elements"`, the API pin,
pricing, locks, idempotency and webhook/security rules are unchanged. See
[Stripe's Endive migration note](https://docs.stripe.com/changelog/endive/2026-09-30/remove-payment-method-types-checkout-sessions).

### Public key and local sandbox setup

Put all real configuration privately in ignored root `.env`. Vite reads this
location through envDir but exposes only its default `VITE_` prefix. Configure
`VITE_STRIPE_PUBLISHABLE_KEY` with the sandbox's publishable test key, matching
the backend's sandbox account. This is the only Stripe key used by browser code.
Never prefix STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET or database values with
VITE_. Restart Vite after environment changes; production bundles bake in the
public value at build time. The frontend deliberately rejects live-key prefixes,
matching the backend's sandbox-only policy. Empty placeholders remain in
`.env.example`; no credentials were supplied or generated for this milestone.

1. Privately configure backend STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET and
   STRIPE_RETURN_URL, plus VITE_STRIPE_PUBLISHABLE_KEY. Keep
   `STRIPE_RETURN_URL=http://localhost:5173/checkout/return` as the generic fallback.
   The client supplies a same-origin, Booking-specific returnUrl to Stripe confirm;
   the fixed backend URL is not an authority signal and contains no secrets.
2. Authenticate/configure the Stripe CLI yourself for that sandbox if necessary.
   No interactive login or CLI listener is started by this implementation.
3. Start webhook forwarding in your own terminal:
   ```zsh
   stripe listen --events checkout.session.completed,checkout.session.expired --forward-to http://localhost:8000/api/v1/webhooks/stripe
   ```
   Copy the listener signing secret privately to ignored `.env`, never into chat,
   source or reports. Restart the backend after changing it. For a deployed
   endpoint, configure snapshot events with the matching pinned API version.
4. Start PAWTEL in two terminals:
   ```zsh
   cd ~/Desktop/PAWTEL/backend
   source .venv/bin/activate
   uvicorn app.main:app --reload
   ```
   ```zsh
   cd ~/Desktop/PAWTEL/frontend
   npm run dev
   ```
5. Follow the README workflow seed instructions with your private demo password.
   Log in as workflow.owner@pawtel.example.com, select active Pets and request
   **Demo workflow garden stay**. Log out and log in as
   workflow.host@pawtel.example.com; accept through the Host inbox.
6. Return as Owner, open the AWAITING_PAYMENT Booking and choose **Pay securely**,
   then **Load secure payment form**. Check dates, Pets, saved subtotal/fee/total,
   Stripe total and the payment deadline. The existing backend may update the
   deadline when it creates the first provider Session; the page re-reads it.
7. Enter only Stripe's documented sandbox test details in the Stripe form. Use
   [Stripe testing scenarios](https://docs.stripe.com/testing) for success,
   declined-card and authentication cases. Do not use real card information and
   do not paste card details into PAWTEL code/tests.
8. Confirm payment. A successful browser result navigates to
   `/account/bookings/:bookingId/payment-return`; redirect-based authentication
   uses the same same-origin path. The return page reads PAWTEL. Only a verified
   completed webhook can make the backend return CONFIRMED.
9. Observe **Your stay is confirmed** after the webhook commits. If pending,
   check forwarding/signing-key/account configuration privately, then refresh.
   Do not create a fake confirmation or treat a standalone CLI-generated event
   as proof: it must match the persisted provider attempt.
10. Also test a decline then retry, logout during checkout, cancellation from
    Booking detail and revisiting an old checkout URL. Resize desktop/tablet/mobile
    and test keyboard access. The form should disappear on logout or observed
    cancellation. A foreign Booking must remain inaccessible.

### Secret lifetime, retries and asynchronous state

Starting checkout sends only `{}` to the existing CSRF-protected endpoint. Its
client secret lives only in the mounted checkout component and Stripe provider;
it is never a Query/Mutation result, storage value, URL parameter or application
log. Unmounting on logout, user/Booking navigation or observed non-payable state
removes the local payment subtree. Late responses after unmount are ignored.
A page reload starts through the protected endpoint again, allowing the existing
backend attempt/session idempotency to resolve reuse safely.

`checkout.confirm({redirect: "if_required", returnUrl: ...})` never updates a
PAWTEL Booking locally. Declines keep the form available for retry while usable.
Initialization/network failures have safe copy and refresh/reload controls; raw
provider exceptions are not printed. Backend window/ineligibility/reconciliation
rejections block further starts on that page. The deadline timer hides the form
without inventing an EXPIRED Booking state; only the backend supplies that state.
A fresh status/deadline read occurs before confirming, but cancellation can still
race a provider operation. Existing backend reconciliation handles that race.

The return page ignores success/session query-string claims and removes unsolicited
return parameters from browser location. It initially shows Checking payment
status, then renders the actual backend state. While AWAITING_PAYMENT it checks at
three-second intervals, bounded to fewer than 30 seconds and at most ten successful
reads. It stops on errors or any other state; manual refresh remains available.
CONFIRMED shows success; EXPIRED, CANCELLED and other states retain their actual
meaning. A generic `/checkout/return` without a Booking ID links to My Bookings
rather than guessing from provider query parameters. No global payment polling.

If a paid event arrives after cancellation, the backend keeps CANCELLED and marks
the attempt for reconciliation. The UI never resurrects the Booking or offers an
automatic refund. Host payouts/Connect and refunds remain outside this milestone.

Automated coverage mocks Stripe at the React boundary and uses the existing backend
fake gateway. No real sandbox success is claimed without manual/provider evidence.
Official implementation references:
[Checkout Elements provider](https://docs.stripe.com/js/react_stripe_js/checkout/checkout_provider),
[Checkout hook](https://docs.stripe.com/js/react_stripe_js/checkout/use_checkout_elements),
[confirmation](https://docs.stripe.com/js/custom_checkout/confirm).

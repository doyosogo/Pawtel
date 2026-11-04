import { ApiError } from '../../lib/api';
import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router';
import { useSession } from '../auth/session';
import { useBookings, type Booking } from '../bookings/api';
import { RequestError } from '../account/RequestError';
import { BookingStatus } from '../bookings/BookingStatus';
import { PaymentSummary } from './PaymentSummary';
import { publishableKey } from './stripe';
import { startCheckout, type CheckoutSession } from './api';
import { StripePaymentForm } from './StripePaymentForm';
import { useDeadline } from './useDeadline';

function PayableCheckout({
  booking,
  reload,
}: {
  booking: Booking;
  reload: () => Promise<Booking>;
}) {
  const [checkout, setCheckout] = useState<CheckoutSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [blocked, setBlocked] = useState(false);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  const expired = useDeadline(
    checkout?.expires_at ?? booking.payment_expires_at,
  );
  const configured = !!publishableKey();
  async function verifyBooking() {
    const latest = await reload();
    const valid =
      latest.status === 'AWAITING_PAYMENT' &&
      !!latest.payment_expires_at &&
      Date.parse(latest.payment_expires_at) > Date.now();
    if (active.current && !valid) {
      setCheckout(null);
      setBlocked(true);
    }
    return valid;
  }
  async function start() {
    if (busy || !configured || expired) return;
    setBusy(true);
    setError(null);
    setBlocked(false);
    try {
      if (!(await verifyBooking()) || !active.current) return;
      const response = await startCheckout(booking.id);
      if (!active.current) return;
      // Re-read after the provider call: it can race a cancellation and extends
      // the backend payment deadline. Never store the response in Query caches.
      if (!(await verifyBooking()) || !active.current) return;
      setCheckout(response);
    } catch (failure) {
      if (active.current) {
        setCheckout(null);
        setError(failure);
        if (
          failure instanceof ApiError &&
          [
            'payment_window_closed',
            'booking_not_payable',
            'payment_reconciliation_required',
            'checkout_not_open',
          ].includes(failure.code)
        )
          setBlocked(true);
      }
    } finally {
      if (active.current) setBusy(false);
    }
  }
  return (
    <section className="workspace-panel" aria-labelledby="secure-payment-title">
      <h2 id="secure-payment-title">Secure payment</h2>
      {!configured ? (
        <p className="notice" role="status">
          Sandbox payment is not configured on this website. Please return to
          your Booking and try again after local payment setup is complete.
        </p>
      ) : expired || blocked ? (
        <p className="notice" role="status">
          This payment window appears closed or the Booking has changed. Refresh
          your Booking status to continue.
        </p>
      ) : checkout ? (
        <StripePaymentForm
          clientSecret={checkout.client_secret}
          booking={booking}
          verifyBooking={verifyBooking}
          retry={() => setCheckout(null)}
        />
      ) : (
        <>
          <p>Load the Stripe payment form to complete your stay payment.</p>
          <button
            className="button"
            disabled={busy}
            onClick={() => void start()}
          >
            {busy ? 'Starting secure payment…' : 'Load secure payment form'}
          </button>
        </>
      )}
      {error != null && (
        <>
          <RequestError error={error} />
          <p>
            <Link to={`/account/bookings/${booking.id}`}>
              Check Booking status
            </Link>{' '}
            before retrying. The backend decides whether another checkout can be
            opened.
          </p>
        </>
      )}
    </section>
  );
}
function OwnerCheckout({ bookingId }: { bookingId: string }) {
  const query = useBookings(false, bookingId);
  const booking = query.data as Booking | undefined;
  async function reload() {
    const result = await query.refetch();
    if (result.error) throw result.error;
    return result.data as Booking;
  }
  if (query.isPending || (!query.isError && !query.isFetchedAfterMount))
    return <p role="status">Checking your Booking…</p>;
  if (query.isError)
    return (
      <RequestError error={query.error} retry={() => void query.refetch()} />
    );
  if (!booking) return null;
  return (
    <>
      <Link className="back-link" to={`/account/bookings/${booking.id}`}>
        ← Booking details
      </Link>
      <div className="section-heading">
        <h1>Pay for your stay</h1>
        <button
          className="button secondary small"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          Refresh Booking status
        </button>
      </div>
      <BookingStatus status={booking.status} />
      <div className="workspace-grid checkout-grid">
        <PaymentSummary booking={booking} />
        {booking.status === 'AWAITING_PAYMENT' ? (
          <PayableCheckout key={booking.id} booking={booking} reload={reload} />
        ) : (
          <section className="workspace-panel">
            <h2>This Booking is not awaiting payment</h2>
            <p>
              Your current status is shown above. A checkout cannot be opened
              for this Booking.
            </p>
            <Link to={`/account/bookings/${booking.id}`}>View Booking</Link>
          </section>
        )}
      </div>
    </>
  );
}
export function CheckoutPage() {
  const { bookingId = '' } = useParams();
  const session = useSession();
  if (session.isPending) return <p role="status">Checking your session…</p>;
  if (session.isError) return <RequestError error={session.error} />;
  if (session.data.state !== 'authenticated')
    return (
      <Navigate
        to={`/login?next=${encodeURIComponent(`/account/bookings/${bookingId}/pay`)}`}
        replace
      />
    );
  // A user/route change unmounts every local secret and Stripe Element.
  return (
    <OwnerCheckout
      key={`${session.data.user.id}:${bookingId}`}
      bookingId={bookingId}
    />
  );
}

import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  actOnBooking,
  bookingUrl,
  useBookings,
  useRefreshBookings,
  type Booking,
} from './api';
import { BookingStatus } from './BookingStatus';
import { aud, listingDetail } from '../listings/api';
import { RequestError } from '../account/RequestError';
export function BookingDetailPage({ host = false }: { host?: boolean }) {
  const { bookingId = '' } = useParams();
  const query = useBookings(host, bookingId);
  const booking = query.data as Booking | undefined;
  const refresh = useRefreshBookings();
  const [cancel, setCancel] = useState(false);
  const listing = useQuery({
    queryKey: ['listing', booking?.listing.id],
    queryFn: ({ signal }) => listingDetail(booking!.listing.id, signal),
    enabled: !!booking && !host,
    retry: false,
  });
  const action = useMutation({
    mutationFn: (name: 'accept' | 'decline' | 'cancel') =>
      actOnBooking(host, bookingId, name),
    retry: false,
    onSuccess: async () => {
      setCancel(false);
      await refresh();
    },
    onError: async () => {
      await refresh();
    },
  });
  if (query.isPending) return <p role="status">Loading booking…</p>;
  if (query.isError)
    return (
      <RequestError error={query.error} retry={() => void query.refetch()} />
    );
  if (!booking) return null;
  const nights = Math.round(
    (Date.parse(booking.check_out) - Date.parse(booking.check_in)) / 86400000,
  );
  return (
    <>
      <Link className="back-link" to={bookingUrl(host)}>
        ← {host ? 'Booking inbox' : 'My Bookings'}
      </Link>
      <div className="section-heading">
        <div>
          <p className="eyebrow">{host ? 'HOST BOOKING' : 'YOUR STAY'}</p>
          <h1>{booking.listing.title}</h1>
          <BookingStatus status={booking.status} />
        </div>
        <button
          className="button secondary small"
          disabled={query.isFetching || action.isPending}
          onClick={() => void query.refetch()}
        >
          Refresh booking
        </button>
      </div>
      {action.isSuccess && <p role="status">Booking updated.</p>}
      {action.isError && <RequestError error={action.error} />}
      <div className="workspace-grid booking-detail-grid">
        <section className="workspace-panel">
          <h2>Stay details</h2>
          <p>
            {booking.listing.suburb}, {booking.listing.state}
          </p>
          <p>
            <strong>Check in:</strong> {booking.check_in}
            <br />
            <strong>Check out:</strong> {booking.check_out}
          </p>
          {host ? (
            <p>Requested by {booking.owner_display_name}</p>
          ) : (
            <p>
              Host:{' '}
              {listing.data?.host.display_name ??
                (listing.isPending
                  ? 'Loading…'
                  : 'Host details are not currently public. Your booking history is preserved.')}
            </p>
          )}
          <h3>Travelling companions</h3>
          <ul>
            {booking.pets.map((p) => (
              <li key={p.id}>
                {p.name} · {p.species === 'DOG' ? 'Dog' : 'Cat'}
                {!p.is_active && ' (archived)'}
              </li>
            ))}
          </ul>
          <Link to={`/stays/${booking.listing.id}`}>View Listing</Link>
        </section>
        <section className="workspace-panel">
          <h2>Your price snapshot</h2>
          <p>
            {nights} night{nights === 1 ? '' : 's'} · {booking.pets.length} pet
            {booking.pets.length === 1 ? '' : 's'}
          </p>
          <dl className="price-breakdown">
            <dt>Accommodation subtotal</dt>
            <dd>{aud(booking.subtotal_cents)} AUD</dd>
            <dt>PAWTEL service fee (10%)</dt>
            <dd>{aud(booking.service_fee_cents)} AUD</dd>
            <dt>Total</dt>
            <dd>
              <strong>{aud(booking.total_cents)} AUD</strong>
            </dd>
          </dl>
          <p className="field-help">
            Saved prices returned by PAWTEL when this request was created.
          </p>
        </section>
      </div>
      {booking.status === 'REQUESTED' && (
        <section className="workspace-panel">
          <h2>
            {host ? 'Review this request' : 'Waiting for the Host to respond'}
          </h2>
          <p>
            A request does not reserve space. The Host checks eligibility and
            available capacity when accepting.
          </p>
          {host && (
            <div className="action-row">
              <button
                className="button"
                disabled={action.isPending}
                onClick={() => action.mutate('accept')}
              >
                Accept request
              </button>
              <button
                className="button secondary"
                disabled={action.isPending}
                onClick={() => action.mutate('decline')}
              >
                Decline request
              </button>
            </div>
          )}
        </section>
      )}
      {booking.status === 'AWAITING_PAYMENT' && (
        <section className="workspace-panel payment-notice">
          <h2>Payment required</h2>
          <p>
            {host ? 'The Owner' : 'You'} must pay {aud(booking.total_cents)} AUD
            before the payment deadline.
          </p>
          {booking.payment_expires_at && (
            <p>
              <strong>Payment deadline:</strong>{' '}
              <time dateTime={booking.payment_expires_at}>
                {new Date(booking.payment_expires_at).toLocaleString('en-AU', {
                  timeZoneName: 'short',
                })}
              </time>
            </p>
          )}
          <p>
            Capacity is temporarily reserved while awaiting payment. The payment
            window can expire.
          </p>
          <p>Secure payment will be connected in the next step.</p>
          <p className="field-help">
            Refresh this booking to check its latest status. Payment processing
            is not available on this website yet.
          </p>
        </section>
      )}
      {!host && ['REQUESTED', 'AWAITING_PAYMENT'].includes(booking.status) && (
        <section className="workspace-panel">
          <h2>Changed your plans?</h2>
          {cancel ? (
            <>
              <p>
                Cancel this booking? Any unpaid capacity hold will be released.
              </p>
              <div className="action-row">
                <button
                  className="button"
                  disabled={action.isPending}
                  onClick={() => action.mutate('cancel')}
                >
                  Confirm cancellation
                </button>
                <button
                  className="button secondary"
                  disabled={action.isPending}
                  onClick={() => setCancel(false)}
                >
                  Keep booking
                </button>
              </div>
            </>
          ) : (
            <button
              className="button secondary"
              disabled={action.isPending}
              onClick={() => setCancel(true)}
            >
              Cancel booking
            </button>
          )}
        </section>
      )}
    </>
  );
}

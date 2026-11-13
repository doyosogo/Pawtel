import { Link, useParams } from 'react-router';
import { useBookings, type Booking } from '../features/bookings/api';
import { BookingStatus } from '../features/bookings/BookingStatus';
import { PaymentSummary } from '../features/payments/PaymentSummary';
import { RequestError } from '../features/account/RequestError';
export function ShowcaseAccess() {
  return (
    <section className="workspace-panel">
      <p className="eyebrow">NO SIGNUP NEEDED</p>
      <h1>Explore PAWTEL your way</h1>
      <p>
        Use Explore as Owner or Explore as Host in the showcase bar. These are
        synthetic UI personas, not real accounts. No email or password is
        needed.
      </p>
      <Link className="button" to="/stays">
        Browse fictional stays
      </Link>
    </section>
  );
}
export function ShowcaseCheckout() {
  const { bookingId = '' } = useParams();
  const query = useBookings(false, bookingId);
  if (query.isPending) return <p role="status">Loading synthetic Booking…</p>;
  if (query.isError) return <RequestError error={query.error} />;
  const booking = query.data as Booking;
  return (
    <>
      <Link className="back-link" to={`/account/bookings/${booking.id}`}>
        ← Booking details
      </Link>
      <h1>Payment preview</h1>
      <BookingStatus status={booking.status} />
      <div className="workspace-grid checkout-grid">
        <PaymentSummary booking={booking} />
        <section className="workspace-panel">
          <h2>Stripe checkout is disabled in the public frontend showcase.</h2>
          <p>
            The full-stack implementation uses Stripe Checkout Elements and
            verified webhooks.
          </p>
          <p>
            No card information is requested and no money is charged. This is a
            simulated UI preview.
          </p>
          <Link to="/account/bookings/showcase-booking-3">
            Preview a separate confirmed example
          </Link>
        </section>
      </div>
    </>
  );
}

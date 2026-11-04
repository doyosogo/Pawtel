import type { Booking } from '../bookings/api';
import { aud } from '../listings/api';
export function PaymentSummary({ booking }: { booking: Booking }) {
  return (
    <section
      className="workspace-panel payment-summary"
      aria-labelledby="payment-summary-title"
    >
      <h2 id="payment-summary-title">{booking.listing.title}</h2>
      <p>
        {booking.listing.suburb}, {booking.listing.state}
      </p>
      <p>
        {booking.check_in} → {booking.check_out}
      </p>
      <ul>
        {booking.pets.map((pet) => (
          <li key={pet.id}>
            {pet.name} · {pet.species === 'DOG' ? 'Dog' : 'Cat'}
          </li>
        ))}
      </ul>
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
      {booking.payment_expires_at && (
        <p>
          Payment deadline:{' '}
          <time dateTime={booking.payment_expires_at}>
            {new Date(booking.payment_expires_at).toLocaleString('en-AU', {
              timeZoneName: 'short',
            })}
          </time>
        </p>
      )}
      {booking.status === 'AWAITING_PAYMENT' && (
        <p className="field-help">
          Capacity is temporarily reserved. Your Booking is confirmed only after
          PAWTEL receives payment confirmation.
        </p>
      )}
    </section>
  );
}

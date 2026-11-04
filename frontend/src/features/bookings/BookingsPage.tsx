import { Link, useSearchParams } from 'react-router';
import { useBookings, bookingUrl, type Booking } from './api';
import { BookingStatus } from './BookingStatus';
import { statusLabels } from './status';
import { aud } from '../listings/api';
import { RequestError } from '../account/RequestError';
export function BookingsPage({ host = false }: { host?: boolean }) {
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? '';
  const offsetValue = Number(params.get('offset') ?? 0);
  const offset =
    Number.isSafeInteger(offsetValue) && offsetValue >= 0 ? offsetValue : 0;
  const query = useBookings(host, undefined, status, offset);
  const items = query.data as Booking[] | undefined;
  function page(next: number) {
    const p = new URLSearchParams(params);
    p.set('offset', String(next));
    setParams(p);
  }
  return (
    <>
      <p className="eyebrow">
        {host ? 'YOUR HOST WORKSPACE' : 'YOUR NEXT LITTLE ADVENTURE'}
      </p>
      <h1>{host ? 'Booking inbox' : 'My Bookings'}</h1>
      <div className="action-row">
        <label className="field">
          Booking status
          <select
            value={status}
            onChange={(e) => {
              const p = new URLSearchParams();
              if (e.target.value) p.set('status', e.target.value);
              setParams(p);
            }}
          >
            <option value="">All statuses</option>
            {Object.entries(statusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button
          className="button secondary small"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          Refresh bookings
        </button>
      </div>
      {query.isPending ? (
        <p role="status">Loading bookings…</p>
      ) : query.isError ? (
        <RequestError error={query.error} retry={() => void query.refetch()} />
      ) : !items?.length ? (
        <p className="notice">
          No bookings on this page.
          {!host && (
            <>
              {' '}
              <Link to="/stays">Find a stay</Link>.
            </>
          )}
        </p>
      ) : (
        <div className="booking-list">
          {items.map((booking) => (
            <article className="workspace-panel booking-row" key={booking.id}>
              <div>
                <BookingStatus status={booking.status} />
                <h2>
                  <Link to={`${bookingUrl(host)}/${booking.id}`}>
                    {booking.listing.title}
                  </Link>
                </h2>
                <p>
                  {booking.listing.suburb}, {booking.listing.state} ·{' '}
                  {booking.check_in} → {booking.check_out}
                </p>
                {host && <p>Requested by {booking.owner_display_name}</p>}
                <p>
                  {booking.pets
                    .map(
                      (p) =>
                        `${p.name} (${p.species === 'DOG' ? 'Dog' : 'Cat'})`,
                    )
                    .join(', ')}
                </p>
              </div>
              <strong>{aud(booking.total_cents)} AUD</strong>
            </article>
          ))}
        </div>
      )}
      <nav className="pagination" aria-label="Booking pages">
        <button
          className="button secondary"
          disabled={offset === 0 || query.isFetching}
          onClick={() => page(Math.max(0, offset - 20))}
        >
          Previous
        </button>
        <span>Page {Math.floor(offset / 20) + 1}</span>
        <button
          className="button secondary"
          disabled={
            query.isFetching || (items?.length ?? 0) < 20 || query.isError
          }
          onClick={() => page(offset + 20)}
        >
          Next
        </button>
      </nav>
    </>
  );
}

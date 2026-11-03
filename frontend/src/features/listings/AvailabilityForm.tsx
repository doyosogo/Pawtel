import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { errorMessage } from '../../lib/api';
import { aud, listingAvailability, type Listing } from './api';
import { localToday, nextDay, validStay } from './search';

export function AvailabilityForm({ listing }: { listing: Listing }) {
  const [url] = useSearchParams();
  const [start, setStart] = useState(url.get('check_in') ?? '');
  const [end, setEnd] = useState(url.get('check_out') ?? '');
  const [count, setCount] = useState(url.get('pet_count') ?? '1');
  const [request, setRequest] = useState('');
  const [validation, setValidation] = useState('');
  const query = useQuery({
    queryKey: ['availability', listing.id, request],
    queryFn: ({ signal }) =>
      listingAvailability(listing.id, new URLSearchParams(request), signal),
    enabled: !!request,
    retry: false,
    staleTime: 0,
  });
  function submit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validStay(start, end)) {
      setValidation('Choose checkout after check-in.');
      return;
    }
    setValidation('');
    const params = new URLSearchParams({
      check_in: start,
      check_out: end,
      pet_count: count,
    });
    if (request === params.toString()) void query.refetch();
    else setRequest(params.toString());
  }
  const current =
    new URLSearchParams({
      check_in: start,
      check_out: end,
      pet_count: count,
    }).toString() === request;
  return (
    <aside className="availability-card" aria-labelledby="availability-title">
      <p className="detail-price">
        <strong>{aud(listing.base_nightly_price_cents)}</strong> AUD{' '}
        <span>/ night</span>
      </p>
      <h2 id="availability-title">A stay that fits your plans</h2>
      <form className="stack" onSubmit={submit}>
        <div className="date-pair">
          <label className="field">
            Check in
            <input
              type="date"
              min={localToday()}
              required
              value={start}
              onChange={(e) => {
                setStart(e.target.value);
                if (end <= e.target.value) setEnd('');
              }}
            />
          </label>
          <label className="field">
            Check out
            <input
              type="date"
              min={start ? nextDay(start) : localToday()}
              required
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
        </div>
        <label className="field">
          Number of pets
          <input
            type="number"
            min={1}
            max={listing.max_pet_capacity}
            required
            value={count}
            onChange={(e) => setCount(e.target.value)}
          />
        </label>
        {validation && (
          <p className="error-text" role="alert">
            {validation}
          </p>
        )}
        <button className="button" disabled={query.isFetching} type="submit">
          {query.isFetching ? 'Checking…' : 'Check availability'}
        </button>
      </form>
      {current && query.data && (
        <div
          className={
            query.data.available
              ? 'availability-result available'
              : 'availability-result unavailable'
          }
          role="status"
        >
          <strong>
            {query.data.available
              ? 'Available for your dates'
              : 'Not available for these dates'}
          </strong>
          <p>
            {query.data.available
              ? 'There’s room for your chosen pets.'
              : 'Try different dates or fewer pets.'}
          </p>
        </div>
      )}
      {current && query.isError && (
        <p className="error-text" role="alert">
          {errorMessage(query.error)}
        </p>
      )}
      <p className="availability-note">
        This check doesn’t reserve a space. A stay is reserved only when the
        host accepts a booking.
      </p>
      <div className="price-note">
        <span>Each additional pet</span>
        <strong>{aud(listing.additional_pet_price_cents)} / night</strong>
      </div>
      <p className="field-help">
        A 10% PAWTEL fee applies to a booking quote. This is a nightly rate, not
        a final quote.
      </p>
      <p className="coming-note">
        Online booking is coming to this website next.
      </p>
    </aside>
  );
}

import { ApiError } from '../../lib/api';
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { useMutation } from '@tanstack/react-query';
import { useSession } from '../auth/session';
import { usePets } from '../pets/api';
import type { Listing } from '../listings/api';
import { validStay } from '../listings/search';
import { requestBooking, useRefreshBookings } from './api';
import { RequestError } from '../account/RequestError';
import { VerificationNotice } from '../account/VerificationNotice';

export function BookingRequest({
  listing,
  start,
  end,
}: {
  listing: Listing;
  start: string;
  end: string;
}) {
  const session = useSession();
  const pets = usePets();
  const location = useLocation();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string[]>([]);
  const [validation, setValidation] = useState('');
  const refresh = useRefreshBookings();
  const mutation = useMutation({
    mutationFn: requestBooking,
    retry: false,
    onSuccess: async (booking) => {
      await refresh();
      navigate(`/account/bookings/${booking.id}`);
    },
  });
  const returnPath = `${location.pathname}?${new URLSearchParams({ check_in: start, check_out: end })}`;
  if (session.isPending) return <p role="status">Checking your session…</p>;
  if (session.isError)
    return (
      <RequestError
        error={session.error}
        retry={() => void session.refetch()}
      />
    );
  if (session.data.state === 'anonymous')
    return (
      <Link
        className="button secondary"
        to={`/login?next=${encodeURIComponent(returnPath)}`}
      >
        Log in to request a stay
      </Link>
    );
  if (session.data.state === 'inactive')
    return (
      <p className="notice">
        This account is inactive. Please log out from the account menu.
      </p>
    );
  if (!session.data.user.email_verified_at) return <VerificationNotice />;
  if (pets.isPending) return <p role="status">Loading your pets…</p>;
  if (pets.isError)
    return (
      <RequestError error={pets.error} retry={() => void pets.refetch()} />
    );
  if (!pets.data.length)
    return (
      <div className="notice">
        <p>Add your companion before requesting a stay.</p>
        <Link to={`/account/pets?next=${encodeURIComponent(returnPath)}`}>
          Add a pet first
        </Link>
      </div>
    );
  const eligible = pets.data.filter(
    (p) => p.is_active && listing.accepted_species.includes(p.species),
  );
  const ids = selected.filter((id) => eligible.some((p) => p.id === id));
  function submit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutation.isPending) return;
    if (
      !validStay(start, end) ||
      start < new Date().toISOString().slice(0, 10)
    ) {
      setValidation(
        'Choose current or future dates above, with checkout after check-in.',
      );
      return;
    }
    if (!ids.length || ids.length > listing.max_pet_capacity) {
      setValidation(
        `Choose between 1 and ${listing.max_pet_capacity} eligible pets.`,
      );
      return;
    }
    setValidation('');
    mutation.mutate({
      listing_id: listing.id,
      check_in: start,
      check_out: end,
      pet_ids: ids,
    });
  }
  return (
    <section className="booking-request" aria-labelledby="request-title">
      <h3 id="request-title">Request this stay</h3>
      <p className="field-help">
        Uses the dates above. Choose your pets; the number selected determines
        your request. Availability is advisory and may change.
      </p>
      <form className="stack" onSubmit={submit}>
        <fieldset className="pet-choices">
          <legend>Who’s coming?</legend>
          {pets.data.map((pet) => (
            <label key={pet.id}>
              <input
                type="checkbox"
                checked={ids.includes(pet.id)}
                disabled={
                  !eligible.some((p) => p.id === pet.id) || mutation.isPending
                }
                onChange={(e) =>
                  setSelected(
                    e.target.checked
                      ? [...new Set([...selected, pet.id])]
                      : selected.filter((id) => id !== pet.id),
                  )
                }
              />{' '}
              {pet.name} · {pet.species === 'DOG' ? 'Dog' : 'Cat'}
              {!listing.accepted_species.includes(pet.species) &&
                ' — species not accepted'}
            </label>
          ))}
        </fieldset>
        <p>
          {ids.length} pet{ids.length === 1 ? '' : 's'} selected ·{' '}
          {start || 'Choose check-in'} → {end || 'Choose checkout'}
        </p>
        {!eligible.length && (
          <p className="notice">
            None of your pets match this Listing. Try another stay or{' '}
            <Link to="/account/pets">manage your pets</Link>.
          </p>
        )}
        {validation && (
          <p className="error-text" role="alert">
            {validation}
          </p>
        )}
        {mutation.isError && (
          <RequestError
            error={mutation.error}
            retry={() => void pets.refetch()}
          />
        )}
        {mutation.isError &&
          mutation.error instanceof ApiError &&
          (mutation.error.status === 0 || mutation.error.status >= 500) && (
            <p className="notice">
              The request outcome may be uncertain.{' '}
              <Link to="/account/bookings">Check My Bookings</Link> before
              submitting again.
            </p>
          )}
        <button
          className="button"
          disabled={mutation.isPending || !eligible.length}
        >
          {mutation.isPending ? 'Submitting…' : 'Request booking'}
        </button>
        <p className="field-help">
          The server will return your price breakdown. No payment is taken when
          requesting.
        </p>
      </form>
    </section>
  );
}

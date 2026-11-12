import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { useMutation } from '@tanstack/react-query';
import { RequestError } from '../account/RequestError';
import { states } from '../listings/search';
import { audInput, centsFromAud } from './money';
import {
  saveListing,
  useHostListings,
  useRefreshHost,
  type HostListing,
  type ListingInput,
} from './api';
import { ListingActions } from './ListingActions';
import { ImageManager } from './ImageManager';
function ListingForm({ listing }: { listing?: HostListing }) {
  const [validation, setValidation] = useState('');
  const navigate = useNavigate();
  const refresh = useRefreshHost();
  const mutation = useMutation({
    mutationFn: (input: Partial<ListingInput>) =>
      saveListing(input, listing?.id),
    onError: refresh,
    onSuccess: async (saved) => {
      await refresh();
      if (!listing)
        navigate(`/host/listings/${saved.id}/edit`, { replace: true });
    },
  });
  function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      const input: ListingInput = {
        title: String(form.get('title')).trim(),
        description: String(form.get('description')).trim(),
        suburb: String(form.get('suburb')).trim(),
        state: String(form.get('state')),
        postcode: String(form.get('postcode')).trim(),
        max_pet_capacity: Number(form.get('capacity')),
        base_nightly_price_cents: centsFromAud(String(form.get('base'))),
        additional_pet_price_cents: centsFromAud(String(form.get('extra'))),
        accepted_species: form.getAll(
          'species',
        ) as ListingInput['accepted_species'],
      };
      if (
        !input.title ||
        !input.description ||
        !input.suburb ||
        !/^\d{4}$/.test(input.postcode) ||
        !Number.isInteger(input.max_pet_capacity) ||
        input.max_pet_capacity < 1 ||
        input.max_pet_capacity > 2147483647
      )
        throw new Error(
          'Check the name, description, location and positive whole-number capacity.',
        );
      const patch = listing
        ? Object.fromEntries(
            Object.entries(input).filter(
              ([key, value]) =>
                JSON.stringify(value) !==
                JSON.stringify(listing[key as keyof ListingInput]),
            ),
          )
        : input;
      if (!Object.keys(patch).length) {
        setValidation('No changes to save.');
        return;
      }
      setValidation('');
      mutation.mutate(patch);
    } catch (error) {
      setValidation(
        error instanceof Error ? error.message : 'Check your details.',
      );
    }
  }
  if (listing?.status === 'ARCHIVED')
    return <ListingActions listing={listing} />;
  return (
    <form className="stack listing-form" onSubmit={submit}>
      <label className="field">
        Listing title
        <input
          name="title"
          required
          maxLength={160}
          defaultValue={listing?.title}
        />
      </label>
      <label className="field">
        Description
        <textarea
          name="description"
          rows={6}
          required
          maxLength={10000}
          defaultValue={listing?.description}
        />
      </label>
      <div className="workspace-grid">
        <label className="field">
          Suburb
          <input
            name="suburb"
            required
            maxLength={100}
            defaultValue={listing?.suburb}
          />
        </label>
        <label className="field">
          State
          <select name="state" defaultValue={listing?.state ?? 'SA'}>
            {states.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Postcode
          <input
            name="postcode"
            required
            inputMode="numeric"
            pattern="[0-9]{4}"
            maxLength={4}
            defaultValue={listing?.postcode}
          />
        </label>
      </div>
      <p className="field-help">
        Australian location fields; postcode/suburb combinations are not
        geographically verified.
      </p>
      <fieldset className="pet-choices">
        <legend>Accepted species</legend>
        {(['DOG', 'CAT'] as const).map((s) => (
          <label key={s}>
            <input
              name="species"
              type="checkbox"
              value={s}
              defaultChecked={listing?.accepted_species.includes(s)}
            />{' '}
            {s === 'DOG' ? 'Dogs' : 'Cats'}
          </label>
        ))}
      </fieldset>
      <p className="field-help">
        A draft may have no species selected. Publishing requires at least one.
      </p>
      <label className="field">
        Maximum pet capacity
        <input
          name="capacity"
          type="number"
          required
          min={1}
          max={2147483647}
          step={1}
          defaultValue={listing?.max_pet_capacity ?? 1}
        />
      </label>
      <p className="field-help">
        Maximum Pets staying at the same time, across all bookings.
      </p>
      <div className="workspace-grid">
        <label className="field">
          Base nightly price (AUD)
          <input
            name="base"
            inputMode="decimal"
            required
            placeholder="55.00"
            defaultValue={
              listing ? audInput(listing.base_nightly_price_cents) : ''
            }
          />
        </label>
        <label className="field">
          Additional-pet nightly price (AUD)
          <input
            name="extra"
            inputMode="decimal"
            required
            placeholder="20.00"
            defaultValue={
              listing ? audInput(listing.additional_pet_price_cents) : '0.00'
            }
          />
        </label>
      </div>
      <p className="field-help">
        Base price covers the first Pet. The additional-pet price applies to
        each extra Pet per night. PAWTEL sets the 10% service fee.
      </p>
      {validation && (
        <p className="error-text" role="alert">
          {validation}
        </p>
      )}
      {mutation.isError && <RequestError error={mutation.error} />}
      <button className="button" disabled={mutation.isPending}>
        {mutation.isPending
          ? 'Saving…'
          : listing
            ? 'Save changes'
            : 'Create draft'}
      </button>
      {mutation.isSuccess && <p role="status">Listing details saved.</p>}
    </form>
  );
}
export function ListingFormPage({ create = false }: { create?: boolean }) {
  const { listingId } = useParams();
  const query = useHostListings(create ? undefined : listingId, '', !create); // Creation needs no existing Listing read.
  if (!create && query.isPending) return <p role="status">Loading Listing…</p>;
  if (!create && query.isError)
    return (
      <RequestError error={query.error} retry={() => void query.refetch()} />
    );
  const listing = create ? undefined : (query.data as HostListing);
  return (
    <>
      <Link to="/host/listings">← My Listings</Link>
      <h1>{create ? 'Create a Listing' : listing?.title}</h1>
      <p>
        {create
          ? 'New Listings are saved as drafts, invisible to guests. Save first, then add photos.'
          : `Status: ${listing?.status}`}
      </p>
      <section className="workspace-panel">
        <ListingForm key={listing?.id ?? 'new'} listing={listing} />
      </section>
      {listing && (
        <>
          <ListingActions listing={listing} />
          {listing.status !== 'ARCHIVED' && <ImageManager listing={listing} />}
        </>
      )}
    </>
  );
}

import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import { ApiError, errorMessage } from '../../lib/api';
import { listingDetail } from './api';
import { ListingGallery } from './ListingGallery';
import { AvailabilityForm } from './AvailabilityForm';

export function ListingDetailPage() {
  const { listingId = '' } = useParams();
  const query = useQuery({
    queryKey: ['listing', listingId],
    queryFn: ({ signal }) => listingDetail(listingId, signal),
    retry: false,
  });
  if (query.isPending)
    return (
      <div
        className="container detail-page"
        role="status"
        aria-label="Loading stay"
      >
        <div className="detail-skeleton" />
        <p>Finding your stay…</p>
      </div>
    );
  if (query.isError)
    return (
      <div className="container feedback" role="alert">
        <h1>
          {query.error instanceof ApiError && query.error.status === 404
            ? 'This stay isn’t available'
            : 'We couldn’t load this stay'}
        </h1>
        <p>{errorMessage(query.error)}</p>
        <Link className="button secondary" to="/stays">
          Explore other stays
        </Link>
      </div>
    );
  const listing = query.data;
  return (
    <article className="container detail-page">
      <Link to="/stays" className="back-link">
        ← All stays
      </Link>
      <div className="detail-heading">
        <p className="eyebrow">A WARM WELCOME IN {listing.state}</p>
        <h1>{listing.title}</h1>
        <p>
          {listing.suburb}, {listing.state} {listing.postcode} · Australia
        </p>
      </div>
      <ListingGallery listing={listing} />
      <div className="detail-layout">
        <div className="detail-content">
          <section className="host-heading">
            <div>
              <h2>A stay hosted by {listing.host.display_name}</h2>
              <p>
                {listing.accepted_species
                  .map((s) => (s === 'DOG' ? 'Dogs' : 'Cats'))
                  .join(' & ')}{' '}
                welcome · Up to {listing.max_pet_capacity} pets
              </p>
            </div>
            <span className="host-avatar" aria-hidden="true">
              {listing.host.display_name.slice(0, 1)}
            </span>
          </section>
          <section className="detail-section">
            <h2>About this stay</h2>
            <p className="description">{listing.description}</p>
          </section>
          <section className="detail-section">
            <h2>Meet your host</h2>
            <h3>{listing.host.display_name}</h3>
            <p>{listing.host.bio ?? 'This host hasn’t added a bio yet.'}</p>
          </section>
          <section className="detail-section stay-notes">
            <h2>A few things to know</h2>
            <p>
              This stay welcomes{' '}
              {listing.accepted_species
                .map((s) => (s === 'DOG' ? 'dogs' : 'cats'))
                .join(' and ')}
              . The capacity shown is the maximum number of pets at a time.
            </p>
            <p>
              Checkout day is not an occupied night. Availability can change
              until a booking is accepted.
            </p>
            {!listing.images?.length && (
              <p className="field-help">
                The illustrations show the mood of this demo, not the actual
                accommodation.
              </p>
            )}
          </section>
        </div>
        <AvailabilityForm listing={listing} />
      </div>
    </article>
  );
}

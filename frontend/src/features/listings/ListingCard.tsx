import { Link, useSearchParams } from 'react-router';
import { aud, type Listing } from './api';
import { ListingMedia } from './ListingMedia';
export function ListingCard({ listing }: { listing: Listing }) {
  const [params] = useSearchParams();
  const stay = new URLSearchParams();
  for (const key of ['check_in', 'check_out', 'pet_count'])
    if (params.has(key)) stay.set(key, params.get(key)!);
  return (
    <article className="listing-card">
      <Link
        to={`/stays/${listing.id}${stay.size ? `?${stay}` : ''}`}
        className="listing-card-link"
      >
        <ListingMedia
          id={listing.id}
          src={listing.images?.[0]?.url}
          alt={listing.images?.[0]?.alt_text}
        />
        <div className="card-location">
          {listing.suburb}, {listing.state}
          <span>
            {listing.accepted_species
              .map((s) => (s === 'DOG' ? 'Dogs' : 'Cats'))
              .join(' & ')}
          </span>
        </div>
        <h3>{listing.title}</h3>
        <p className="card-host">Hosted by {listing.host.display_name}</p>
        <p className="card-price">
          <strong>{aud(listing.base_nightly_price_cents)}</strong> AUD{' '}
          <span>/ night</span>
        </p>
      </Link>
    </article>
  );
}

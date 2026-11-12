import { Link, useSearchParams } from 'react-router';
import { useHostListings, type HostListing } from './api';
import { ListingActions } from './ListingActions';
import { RequestError } from '../account/RequestError';
import { ListingMedia } from '../listings/ListingMedia';
import { aud } from '../listings/api';
export function HostListingsPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? '';
  const query = useHostListings(undefined, status);
  const items = query.data as HostListing[] | undefined;
  return (
    <>
      <h1>My Listings</h1>
      <div className="action-row">
        <Link className="button" to="/host/listings/new">
          Create Listing
        </Link>
        <label className="field">
          Listing status
          <select
            value={status}
            onChange={(e) =>
              setParams(e.target.value ? { status: e.target.value } : {})
            }
          >
            <option value="">Active Listings</option>
            <option value="DRAFT">Draft</option>
            <option value="PUBLISHED">Published</option>
            <option value="ARCHIVED">Archived</option>
          </select>
        </label>
      </div>
      {query.isPending ? (
        <p role="status">Loading Listings…</p>
      ) : query.isError ? (
        <RequestError error={query.error} retry={() => void query.refetch()} />
      ) : !items?.length ? (
        <p className="notice">
          No Listings here yet. Create a draft to get started.
        </p>
      ) : (
        <div className="workspace-grid">
          {items.map((listing) => (
            <article className="workspace-panel" key={listing.id}>
              <ListingMedia
                id={listing.id}
                src={listing.images?.[0]?.url}
                alt={listing.images?.[0]?.alt_text}
              />
              <h2>{listing.title}</h2>
              <p>
                {listing.suburb}, {listing.state} · {listing.status}
              </p>
              <p>
                {aud(listing.base_nightly_price_cents)} AUD / night ·{' '}
                {listing.accepted_species.join(' & ') || 'No species selected'}
              </p>
              <Link to={`/host/listings/${listing.id}/edit`}>
                {listing.status === 'ARCHIVED'
                  ? 'View archived Listing'
                  : 'Edit Listing & photos'}
              </Link>
              <ListingActions listing={listing} />
            </article>
          ))}
        </div>
      )}
    </>
  );
}

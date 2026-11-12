import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { write } from '../../lib/api';
import { RequestError } from '../account/RequestError';
import { useRefreshHost, type HostListing } from './api';
export function ListingActions({ listing }: { listing: HostListing }) {
  const [confirm, setConfirm] = useState(false);
  const refresh = useRefreshHost();
  const mutation = useMutation({
    mutationFn: (action: 'publish' | 'draft' | 'archive') =>
      write(
        `/host/listings/${listing.id}`,
        action === 'archive'
          ? {}
          : { status: action === 'publish' ? 'PUBLISHED' : 'DRAFT' },
        action === 'archive' ? 'DELETE' : 'PATCH',
      ),
    onSuccess: async () => {
      setConfirm(false);
      await refresh();
    },
    onError: refresh,
  });
  if (listing.status === 'ARCHIVED')
    return (
      <p>Archived Listings are read-only and preserved for Booking history.</p>
    );
  return (
    <div>
      {listing.status === 'DRAFT' && (
        <p className="field-help">
          Draft Listings are not visible to guests. Choose at least one accepted
          species before publishing.
        </p>
      )}
      <div className="action-row">
        <button
          className="button small"
          disabled={mutation.isPending}
          onClick={() =>
            mutation.mutate(listing.status === 'DRAFT' ? 'publish' : 'draft')
          }
        >
          {listing.status === 'DRAFT' ? 'Publish listing' : 'Move to draft'}
        </button>
        <button
          className="button secondary small"
          disabled={mutation.isPending}
          onClick={() => setConfirm(true)}
        >
          Archive listing
        </button>
      </div>
      {confirm && (
        <div className="notice">
          <p>
            Archive this Listing? It disappears from public discovery and
            becomes read-only. Booking history is preserved.
          </p>
          <button
            className="button small"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate('archive')}
          >
            Confirm archive
          </button>{' '}
          <button
            className="button secondary small"
            disabled={mutation.isPending}
            onClick={() => setConfirm(false)}
          >
            Keep listing
          </button>
        </div>
      )}
      {mutation.isError && <RequestError error={mutation.error} />}
      {mutation.isSuccess && <p role="status">Listing updated.</p>}
    </div>
  );
}

import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router';
import { ApiError, errorMessage } from '../../lib/api';
import { listings } from './api';
import { apiSearch } from './search';
import { ListingCard } from './ListingCard';

export function Results({ home = false }: { home?: boolean }) {
  const [params, setParams] = useSearchParams();
  const search = apiSearch(home ? new URLSearchParams() : params);
  const query = useQuery({
    queryKey: ['listings', search.toString()],
    queryFn: ({ signal }) => listings(search, signal),
    staleTime: 30_000,
    retry: false,
  });
  if (query.isPending)
    return (
      <div className="listing-grid" aria-label="Loading stays" role="status">
        {Array.from({ length: 8 }, (_, i) => (
          <div className="card-skeleton" key={i}>
            <div />
            <span />
            <span />
            <span />
          </div>
        ))}
      </div>
    );
  if (query.isError)
    return (
      <div className="feedback" role="alert">
        <h2>
          {query.error instanceof ApiError && query.error.status === 422
            ? 'Let’s check those filters'
            : 'We couldn’t load stays'}
        </h2>
        <p>{errorMessage(query.error)}</p>
        <button
          className="button secondary"
          onClick={() => void query.refetch()}
        >
          Try again
        </button>{' '}
        <Link to="/stays" className="text-link">
          Reset search
        </Link>
      </div>
    );
  if (!query.data.items.length)
    return (
      <div className="feedback">
        <span className="empty-paw">♡</span>
        <h2>No stays found this time</h2>
        <p>Try another suburb or state, different dates, or fewer filters.</p>
        <Link className="button secondary" to="/stays">
          Explore all stays
        </Link>
      </div>
    );
  function page(offset: number) {
    const next = new URLSearchParams(params);
    next.set('offset', String(offset));
    setParams(next);
    document.getElementById('results-heading')?.focus();
  }
  return (
    <>
      <div className="listing-grid">
        {query.data.items.map((listing) => (
          <ListingCard key={listing.id} listing={listing} />
        ))}
      </div>
      {home ? (
        <div className="explore-more">
          <Link className="button secondary" to="/stays">
            Explore more stays <span aria-hidden="true">→</span>
          </Link>
        </div>
      ) : (
        <nav className="pagination" aria-label="Results pages">
          <button
            className="button secondary"
            disabled={query.data.offset === 0}
            onClick={() =>
              page(Math.max(0, query.data.offset - query.data.limit))
            }
          >
            Previous
          </button>
          <span>
            Page {Math.floor(query.data.offset / query.data.limit) + 1}
          </span>
          <button
            className="button secondary"
            disabled={!query.data.has_more}
            onClick={() => page(query.data.next_offset!)}
          >
            Next
          </button>
        </nav>
      )}
    </>
  );
}

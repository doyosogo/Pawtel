import { screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ListingDetailPage } from './ListingPage';
import { renderPage } from '../../test/render';
import { json, listing } from '../../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
it('loads the actual detail contract and shows truthful imagery and nightly pricing', async () => {
  const fetcher = vi.fn().mockResolvedValue(json(listing));
  vi.stubGlobal('fetch', fetcher);
  renderPage(<ListingDetailPage />, {
    path: `/stays/${listing.id}`,
    route: '/stays/:listingId',
  });
  expect(screen.getByLabelText('Loading stay')).toBeInTheDocument();
  expect(
    await screen.findByRole('heading', { name: listing.title }),
  ).toBeInTheDocument();
  expect(screen.getByText(listing.description)).toBeInTheDocument();
  expect(screen.getByText(/A stay hosted by Riley/)).toBeInTheDocument();
  expect(screen.getAllByText('Demo illustration')).toHaveLength(2);
  expect(screen.getByText('$52')).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledWith(
    `/api/v1/listings/${listing.id}`,
    expect.objectContaining({ credentials: 'include' }),
  );
});
it('handles missing listings without showing accommodation data', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      json(
        {
          error: { code: 'listing_not_found', message: 'Listing not found.' },
        },
        404,
      ),
    ),
  );
  renderPage(<ListingDetailPage />, {
    path: '/stays/missing',
    route: '/stays/:listingId',
  });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'This stay isn’t available',
  );
  expect(
    screen.queryByRole('button', { name: 'Check availability' }),
  ).not.toBeInTheDocument();
});

import { fireEvent, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { HomePage } from './HomePage';
import { renderPage } from '../test/render';
import { json, listing, page } from '../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
it('renders real API stays without fictional ratings', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(page())));
  renderPage(<HomePage />);
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
    'A little holiday',
  );
  expect(
    await screen.findByRole('heading', { name: listing.title }),
  ).toBeInTheDocument();
  expect(screen.getByText('Hosted by Riley')).toBeInTheDocument();
  expect(screen.queryByText(/reviews/i)).not.toBeInTheDocument();
});
it('navigates search with both selected species and a structured postcode', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(page())));
  renderPage(<HomePage />, { route: '/' });
  fireEvent.change(screen.getByLabelText('Where'), {
    target: { value: '0800' },
  });
  fireEvent.click(screen.getByLabelText('Dogs'));
  fireEvent.click(screen.getByLabelText('Cats'));
  fireEvent.click(screen.getByRole('button', { name: 'Search stays' }));
  expect(screen.getAllByLabelText('Current location')[0]).toHaveTextContent(
    '/stays?postcode=0800&pet_count=1&species=DOG&species=CAT',
  );
});
it('shows empty results rather than mock stays', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(page([]))));
  renderPage(<HomePage />);
  expect(
    await screen.findByRole('heading', { name: 'No stays found this time' }),
  ).toBeInTheDocument();
});
it('offers retry for a failed public API call', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      json({ error: { code: 'internal_error', message: 'Unavailable' } }, 503),
    )
    .mockResolvedValue(json(page()));
  vi.stubGlobal('fetch', fetcher);
  renderPage(<HomePage />);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'couldn’t load stays',
  );
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(
    await screen.findByRole('heading', { name: listing.title }),
  ).toBeInTheDocument();
});

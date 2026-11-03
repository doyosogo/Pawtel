import { fireEvent, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AvailabilityForm } from './AvailabilityForm';
import { renderPage } from '../../test/render';
import { json, listing } from '../../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
it('checks real availability and hides stale results after editing', async () => {
  const fetcher = vi.fn().mockResolvedValue(
    json({
      listing_id: listing.id,
      check_in: '2029-11-10',
      check_out: '2029-11-12',
      pet_count: 1,
      available: true,
      remaining_capacity_at_tightest_point: 2,
    }),
  );
  vi.stubGlobal('fetch', fetcher);
  renderPage(<AvailabilityForm listing={listing} />);
  fireEvent.change(screen.getByLabelText('Check in'), {
    target: { value: '2029-11-10' },
  });
  fireEvent.change(screen.getByLabelText('Check out'), {
    target: { value: '2029-11-12' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Check availability' }));
  expect(
    await screen.findByText('Available for your dates'),
  ).toBeInTheDocument();
  expect(fetcher.mock.calls[0][0]).toContain(
    '/availability?check_in=2029-11-10&check_out=2029-11-12&pet_count=1',
  );
  expect(screen.getByText(/doesn’t reserve a space/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Number of pets'), {
    target: { value: '2' },
  });
  expect(
    screen.queryByText('Available for your dates'),
  ).not.toBeInTheDocument();
});

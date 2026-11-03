import { fireEvent, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Results } from './Results';
import { renderPage } from '../../test/render';
import { json, page } from '../../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
it('requests backend pagination rather than filtering all data locally', async () => {
  const fetcher = vi
    .fn()
    .mockImplementation((url: string) =>
      Promise.resolve(
        json(
          url.includes('offset=8')
            ? { ...page(), offset: 8 }
            : { ...page(), has_more: true, next_offset: 8 },
        ),
      ),
    );
  vi.stubGlobal('fetch', fetcher);
  renderPage(<Results />, { path: '/stays?species=DOG&species=CAT' });
  await screen.findByText('Page 1');
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByText('Page 2');
  expect(fetcher.mock.calls.at(-1)![0]).toContain('offset=8');
  expect(fetcher.mock.calls.at(-1)![0]).toContain('species=DOG&species=CAT');
});
it('exposes an accessible loading state while the API is pending', () => {
  vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
  renderPage(<Results />);
  expect(screen.getByLabelText('Loading stays')).toHaveAttribute(
    'role',
    'status',
  );
  expect(
    screen.queryByText('No stays found this time'),
  ).not.toBeInTheDocument();
});

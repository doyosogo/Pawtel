import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StaysPage } from './StaysPage';
import { renderPage } from '../test/render';
import { json, page } from '../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
it('converts AUD price inputs to API cents and resets pagination', async () => {
  const fetcher = vi.fn().mockResolvedValue(json(page()));
  vi.stubGlobal('fetch', fetcher);
  renderPage(<StaysPage />, {
    path: '/stays?state=SA&offset=8&min_price_cents=1000',
  });
  expect(screen.getByLabelText('Minimum AUD')).toHaveValue(10);
  fireEvent.change(screen.getByLabelText('Minimum AUD'), {
    target: { value: '52.50' },
  });
  fireEvent.change(screen.getByLabelText('Maximum AUD'), {
    target: { value: '80' },
  });
  fireEvent.submit(screen.getByLabelText('Minimum AUD').closest('form')!);
  await waitFor(() =>
    expect(fetcher.mock.calls.at(-1)![0]).toContain('min_price_cents=5250'),
  );
  expect(fetcher.mock.calls.at(-1)![0]).toContain('max_price_cents=8000');
  expect(fetcher.mock.calls.at(-1)![0]).toContain('state=SA');
  expect(fetcher.mock.calls.at(-1)![0]).not.toContain('offset=8');
});

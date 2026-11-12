import { screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { renderPage } from '../test/render';
import { DemoNotice } from './DemoNotice';
import { AuthPage } from '../features/auth/AuthPage';
import { anonymous, json } from '../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
it('labels public demo and truthfully disables registration/email', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        json({ portfolio_demo: true, registration_enabled: false }),
      ),
  );
  renderPage(<DemoNotice />);
  expect(await screen.findByLabelText('Portfolio demo')).toHaveTextContent(
    'No real bookings or charges',
  );
});
it('hides registration form when server disables it', async () => {
  const fetcher = vi
    .fn()
    .mockImplementation((url: string) =>
      Promise.resolve(
        url.endsWith('/config')
          ? json({ portfolio_demo: true, registration_enabled: false })
          : anonymous(),
      ),
    );
  vi.stubGlobal('fetch', fetcher);
  renderPage(<AuthPage register />);
  expect(
    await screen.findByRole('heading', { name: 'Registration unavailable' }),
  ).toBeVisible();
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
  expect(
    fetcher.mock.calls.every(([path]) => !String(path).endsWith('/register')),
  ).toBe(true);
});
it('fails closed with truthful copy when configuration cannot load', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
  renderPage(<AuthPage register />);
  expect(
    await screen.findByText(/Registration availability could not be checked/),
  ).toBeVisible();
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
});

import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Header } from './Header';
import { renderPage } from '../test/render';
import { anonymous, json, user } from '../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
it('waits for session before showing account-specific actions', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(anonymous()));
  renderPage(<Header />);
  fireEvent.click(screen.getByRole('button', { name: 'Account menu' }));
  expect(
    await screen.findByRole('link', { name: 'Log in' }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Log out' }),
  ).not.toBeInTheDocument();
});
it('labels an existing host honestly and server-logs out, clearing private data', async () => {
  let logged = true;
  const fetcher = vi.fn().mockImplementation((url: string) => {
    if (url.endsWith('/logout')) {
      logged = false;
      return Promise.resolve(new Response(null, { status: 204 }));
    }
    if (url.endsWith('/csrf'))
      return Promise.resolve(json({ csrf_token: 'nonce' }));
    if (url.endsWith('/host/profile'))
      return Promise.resolve(
        json({
          user_id: user.id,
          bio: 'Host bio',
          created_at: '',
          updated_at: '',
        }),
      );
    return Promise.resolve(
      logged
        ? json({ ...user, email_verified_at: '2026-01-01T00:00:00Z' })
        : anonymous(),
    );
  });
  vi.stubGlobal('fetch', fetcher);
  const { client } = renderPage(<Header />);
  expect(
    await screen.findByRole('link', { name: 'Your host space' }),
  ).toBeInTheDocument();
  client.setQueryDefaults(['private-pets'], { meta: { private: true } });
  client.setQueryData(['private-pets'], [{ id: 'private' }]);
  fireEvent.click(screen.getByRole('button', { name: 'Account menu' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Log out' }));
  await waitFor(() =>
    expect(client.getQueryData(['private-pets'])).toBeUndefined(),
  );
  expect(fetcher.mock.calls.some((call) => call[0].endsWith('/logout'))).toBe(
    true,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Account menu' }));
  expect(
    await screen.findByRole('link', { name: 'Log in' }),
  ).toBeInTheDocument();
});

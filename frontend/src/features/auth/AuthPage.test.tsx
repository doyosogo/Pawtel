import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AuthPage } from './AuthPage';
import { renderPage } from '../../test/render';
import { anonymous, json, user } from '../../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
it('registers with truthful email-delivery copy and clears password input', async () => {
  const fetcher = vi
    .fn()
    .mockImplementation((url: string) =>
      Promise.resolve(
        url.endsWith('/register')
          ? json({ user, verification_delivery: 'not_configured' }, 201)
          : anonymous(),
      ),
    );
  vi.stubGlobal('fetch', fetcher);
  renderPage(<AuthPage register />, { path: '/register' });
  await screen.findByRole('button', { name: 'Create account' });
  fireEvent.change(screen.getByLabelText('Your name'), {
    target: { value: 'Alex' },
  });
  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: 'alex@example.test' },
  });
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'a synthetic long passphrase' },
  });
  await screen.findByText('Create account');
  // Wait for initial session query before submitting.
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Create account' }),
    ).toBeEnabled(),
  );
  fireEvent.submit(screen.getByLabelText('Password').closest('form')!);
  expect(
    await screen.findByRole('heading', { name: 'You’re part of PAWTEL.' }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/no verification email has been sent/),
  ).toBeInTheDocument();
  expect(screen.queryByText(/check your inbox/i)).not.toBeInTheDocument();
});
it('handles generic invalid login and does not cache passwords', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        url.endsWith('/login')
          ? json(
              {
                error: {
                  code: 'invalid_credentials',
                  message: 'Email or password is incorrect.',
                },
              },
              401,
            )
          : anonymous(),
      ),
    ),
  );
  const { client } = renderPage(<AuthPage />);
  await screen.findByText('Log in to your PAWTEL account.');
  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: 'alex@example.test' },
  });
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'wrong-password' },
  });
  fireEvent.submit(screen.getByLabelText('Password').closest('form')!);
  expect(await screen.findByRole('alert')).toHaveTextContent('don’t match');
  expect(screen.getByLabelText('Password')).toHaveValue('');
  expect(client.getMutationCache().getAll()).toHaveLength(0);
});
it('logs in with a cookie session and navigates without an external redirect', async () => {
  let logged = false;
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) => {
      if (url.endsWith('/login')) {
        logged = true;
        return Promise.resolve(json(user));
      }
      return Promise.resolve(logged ? json(user) : anonymous());
    }),
  );
  renderPage(<AuthPage />, {
    path: '/login?next=https://example.com',
    route: '/login',
  });
  await screen.findByText('Log in to your PAWTEL account.');
  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: 'alex@example.test' },
  });
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'a synthetic long passphrase' },
  });
  fireEvent.submit(screen.getByLabelText('Password').closest('form')!);
  expect(await screen.findAllByLabelText('Current location')).toBeTruthy();
  await screen.findAllByText('/stays');
});
it('updates current-user state without writing credentials to browser storage', async () => {
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  let logged = false;
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) => {
      if (url.endsWith('/login')) logged = true;
      return Promise.resolve(logged ? json(user) : anonymous());
    }),
  );
  const { client } = renderPage(<AuthPage />, {
    path: '/login',
    route: '/login',
  });
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Log in' })).toBeEnabled(),
  );
  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: user.email },
  });
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'synthetic password only' },
  });
  fireEvent.submit(screen.getByLabelText('Password').closest('form')!);
  await waitFor(() =>
    expect(client.getQueryData(['session'])).toEqual({
      state: 'authenticated',
      user,
    }),
  );
  expect(storage).not.toHaveBeenCalled();
  expect(
    JSON.stringify(
      client
        .getQueryCache()
        .getAll()
        .map((q) => q.state.data),
    ),
  ).not.toContain('synthetic password only');
  expect(client.getMutationCache().getAll()).toHaveLength(0);
  storage.mockRestore();
});

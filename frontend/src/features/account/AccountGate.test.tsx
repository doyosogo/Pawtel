import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { AccountGate } from './AccountGate';
import { HostGate } from '../host/HostPage';
import { renderPage } from '../../test/render';
import { mockWorkflow } from '../../test/workflow';
import { anonymous, json, user } from '../../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
it('redirects private visitors to login with the original route', async () => {
  mockWorkflow((path) => (path.endsWith('/auth/me') ? anonymous() : undefined));
  renderPage(<AccountGate />, {
    path: '/account/pets?next=stay',
    route: '/account/pets',
  });
  await screen.findAllByText('/login?next=%2Faccount%2Fpets%3Fnext%3Dstay');
});
it('blocks unverified booking routes with truthful guidance', async () => {
  mockWorkflow((path) => (path.endsWith('/auth/me') ? json(user) : undefined));
  renderPage(<AccountGate verified />);
  expect(
    await screen.findByText(/Verified email is required/),
  ).toHaveTextContent('Email delivery is not configured');
});
it('shows a proper non-host state instead of fetching an inbox', async () => {
  const fetcher = mockWorkflow((path) =>
    path.endsWith('/host/profile')
      ? json(
          {
            error: {
              code: 'host_profile_not_found',
              message: 'No Host profile.',
            },
          },
          404,
        )
      : undefined,
  );
  renderPage(
    <Routes>
      <Route element={<HostGate />}>
        <Route path="*" element={<p>Inbox should not render</p>} />
      </Route>
    </Routes>,
  );
  expect(
    await screen.findByText(/You do not have a Host profile/),
  ).toBeInTheDocument();
  expect(screen.queryByText('Inbox should not render')).not.toBeInTheDocument();
  expect(
    fetcher.mock.calls.some(([path]) => path.includes('/host/bookings')),
  ).toBe(false);
});

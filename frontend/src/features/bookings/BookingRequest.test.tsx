import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { BookingRequest } from './BookingRequest';
import { renderPage } from '../../test/render';
import { booking, dog, mockWorkflow } from '../../test/workflow';
import { json, listing, user, anonymous } from '../../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
const request = () => (
  <BookingRequest listing={listing} start="2029-11-10" end="2029-11-12" />
);
it('submits only selected pets/dates/listing and navigates to server booking', async () => {
  const fetcher = mockWorkflow((path, init) =>
    path.endsWith('/bookings') && init?.method === 'POST'
      ? json(booking, 201)
      : undefined,
  );
  const { client } = renderPage(request(), {
    path: `/stays/${listing.id}`,
    route: '/stays/:id',
  });
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  fireEvent.click(await screen.findByLabelText(/Milo · Dog/));
  fireEvent.click(screen.getByLabelText(/Luna · Cat/));
  fireEvent.click(screen.getByLabelText(/Luna · Cat/));
  fireEvent.click(screen.getByRole('button', { name: 'Request booking' }));
  await screen.findAllByText('/account/bookings/booking-id');
  const call = fetcher.mock.calls.find(
    ([path, init]) => path.endsWith('/bookings') && init?.method === 'POST',
  )!;
  expect(JSON.parse(call[1].body)).toEqual({
    listing_id: listing.id,
    pet_ids: [dog.id],
    check_in: '2029-11-10',
    check_out: '2029-11-12',
  });
  expect(call[1].headers).toMatchObject({
    'X-CSRF-Token': 'nonce',
    'X-PAWTEL-Request': '1',
  });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['bookings'] });
});
it('provides Add a pet first when no active pets exist', async () => {
  mockWorkflow((path) => (path.includes('/pets?') ? json([]) : undefined));
  renderPage(request());
  expect(
    await screen.findByRole('link', { name: 'Add a pet first' }),
  ).toHaveAttribute('href', expect.stringContaining('/account/pets?next='));
  expect(
    screen.queryByRole('button', { name: 'Request booking' }),
  ).not.toBeInTheDocument();
});
it('disables unsupported species and never submits those pets', async () => {
  const fetcher = mockWorkflow();
  renderPage(
    <BookingRequest
      listing={{ ...listing, accepted_species: ['DOG'] }}
      start="2029-11-10"
      end="2029-11-12"
    />,
  );
  expect(await screen.findByLabelText(/Luna · Cat/)).toBeDisabled();
  fireEvent.submit(
    screen.getByRole('button', { name: 'Request booking' }).closest('form')!,
  );
  expect(await screen.findByRole('alert')).toHaveTextContent('eligible pets');
  expect(fetcher.mock.calls.some(([path]) => path.endsWith('/bookings'))).toBe(
    false,
  );
});
it('rejects invalid stay dates before requesting', async () => {
  const fetcher = mockWorkflow();
  renderPage(
    <BookingRequest listing={listing} start="2029-11-12" end="2029-11-10" />,
  );
  fireEvent.click(await screen.findByLabelText(/Milo · Dog/));
  fireEvent.click(screen.getByRole('button', { name: 'Request booking' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'checkout after check-in',
  );
  expect(fetcher.mock.calls.some(([path]) => path.endsWith('/bookings'))).toBe(
    false,
  );
});
it.each([
  'booking_capacity_unavailable',
  'pet_not_available',
  'listing_unavailable',
  'email_not_verified',
  'network_error',
])('handles request failure %s', async (code) => {
  mockWorkflow((path, init) =>
    path.endsWith('/bookings') && init?.method === 'POST'
      ? json(
          { error: { code, message: 'Request failed.' } },
          code === 'network_error' ? 503 : 409,
        )
      : undefined,
  );
  renderPage(request());
  fireEvent.click(await screen.findByLabelText(/Milo · Dog/));
  fireEvent.click(screen.getByRole('button', { name: 'Request booking' }));
  const copy: Record<string, string> = {
    booking_capacity_unavailable: 'Those dates are no longer available',
    pet_not_available: 'no longer eligible',
    listing_unavailable: 'Listing is no longer available',
    email_not_verified: 'Email delivery is not configured',
    network_error: 'taking a moment',
  };
  await waitFor(() =>
    expect(screen.getByText(new RegExp(copy[code]))).toBeInTheDocument(),
  );
});
it('gives truthful verification guidance without allowing a request', async () => {
  mockWorkflow((path) => (path.endsWith('/auth/me') ? json(user) : undefined));
  renderPage(request());
  expect(
    await screen.findByText(/Verified email is required/),
  ).toHaveTextContent('no verification email has been sent');
  expect(
    screen.queryByRole('button', { name: 'Request booking' }),
  ).not.toBeInTheDocument();
});
it('preserves dates through login return navigation', async () => {
  mockWorkflow((path) => (path.endsWith('/auth/me') ? anonymous() : undefined));
  renderPage(request(), { path: `/stays/${listing.id}` });
  expect(
    await screen.findByRole('link', { name: 'Log in to request a stay' }),
  ).toHaveAttribute('href', expect.stringContaining('check_in%3D2029-11-10'));
});
it('clears private session state on an authentication failure', async () => {
  mockWorkflow((path, init) =>
    path.endsWith('/bookings') && init?.method === 'POST'
      ? anonymous()
      : undefined,
  );
  const { client } = renderPage(request());
  fireEvent.click(await screen.findByLabelText(/Milo · Dog/));
  fireEvent.click(screen.getByRole('button', { name: 'Request booking' }));
  expect(
    await screen.findByRole('link', { name: 'Log in to request a stay' }),
  ).toBeInTheDocument();
  expect(client.getQueryData(['session'])).toEqual({ state: 'anonymous' });
});

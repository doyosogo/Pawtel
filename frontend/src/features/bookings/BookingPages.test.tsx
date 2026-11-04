import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { BookingsPage } from './BookingsPage';
import { BookingDetailPage } from './BookingDetailPage';
import { renderPage } from '../../test/render';
import { booking, mockWorkflow } from '../../test/workflow';
import { json } from '../../test/fixtures';
import type { BookingStatus } from './api';
import { statusLabels } from './status';
afterEach(() => vi.unstubAllGlobals());
const detail = (host = false) =>
  renderPage(<BookingDetailPage host={host} />, {
    path: `${host ? '/host' : '/account'}/bookings/booking-id`,
    route: `${host ? '/host' : '/account'}/bookings/:bookingId`,
  });
it('renders owner collection, status filtering and server pagination', async () => {
  const fetcher = mockWorkflow((path) =>
    path.includes('/bookings?') ? json([booking]) : undefined,
  );
  renderPage(<BookingsPage />);
  expect(
    await screen.findByRole('link', { name: booking.listing.title }),
  ).toHaveAttribute('href', '/account/bookings/booking-id');
  expect(
    screen.getByText('Waiting for host', { selector: 'span' }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Booking status'), {
    target: { value: 'REQUESTED' },
  });
  await waitFor(() =>
    expect(fetcher.mock.calls.at(-1)![0]).toContain('status=REQUESTED'),
  );
});
it.each<BookingStatus>([
  'REQUESTED',
  'DECLINED',
  'AWAITING_PAYMENT',
  'CONFIRMED',
  'CANCELLED',
  'EXPIRED',
  'PAYMENT_FAILED',
  'COMPLETED',
])('renders real backend status %s', async (status) => {
  mockWorkflow((path) =>
    path.includes('/bookings?') ? json([{ ...booking, status }]) : undefined,
  );
  renderPage(<BookingsPage />);
  await screen.findByRole('link', { name: booking.listing.title });
  expect(screen.getByText('$114.40 AUD')).toBeInTheDocument();
  expect(
    screen.getByText(statusLabels[status], { selector: 'span' }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: /pay|checkout/i }),
  ).not.toBeInTheDocument();
});
it('shows returned owner detail snapshot and safe public Host name', async () => {
  mockWorkflow((path) =>
    path.endsWith('/bookings/booking-id') ? json(booking) : undefined,
  );
  detail();
  expect(
    await screen.findByRole('heading', { name: booking.listing.title }),
  ).toBeInTheDocument();
  expect(screen.getByText('$104 AUD')).toBeInTheDocument();
  expect(screen.getByText('$10.40 AUD')).toBeInTheDocument();
  expect(screen.getByText('2 nights · 1 pet')).toBeInTheDocument();
  expect(await screen.findByText('Host: Riley')).toBeInTheDocument();
  expect(
    screen.getByText('Waiting for the Host to respond'),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: /pay/i }),
  ).not.toBeInTheDocument();
});
it('cancels explicitly after confirmation and refetches booking state', async () => {
  let cancelled = false;
  const fetcher = mockWorkflow((path, init) => {
    if (path.endsWith('/cancel') && init?.method === 'POST') {
      cancelled = true;
      return json({ ...booking, status: 'CANCELLED' });
    }
    if (path.endsWith('/bookings/booking-id'))
      return json({
        ...booking,
        status: cancelled ? 'CANCELLED' : 'REQUESTED',
      });
  });
  const { client } = detail();
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  fireEvent.click(
    await screen.findByRole('button', { name: 'Cancel booking' }),
  );
  expect(fetcher.mock.calls.some(([path]) => path.endsWith('/cancel'))).toBe(
    false,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Confirm cancellation' }));
  expect(await screen.findByText('Cancelled')).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Cancel booking' }),
  ).not.toBeInTheDocument();
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['bookings'] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['availability'] });
  expect(
    JSON.parse(
      fetcher.mock.calls.find(([path]) => path.endsWith('/cancel'))![1].body,
    ),
  ).toEqual({});
});
it('presents payment deadline and reservation without Stripe calls', async () => {
  const fetcher = mockWorkflow((path) =>
    path.endsWith('/bookings/booking-id')
      ? json({
          ...booking,
          status: 'AWAITING_PAYMENT',
          payment_expires_at: '2029-11-01T12:00:00Z',
        })
      : undefined,
  );
  detail();
  expect(
    await screen.findByRole('heading', { name: 'Payment required' }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Capacity is temporarily reserved/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('link', { name: 'Pay securely' }),
  ).toBeInTheDocument();
  expect(screen.getByText('Payment deadline:')).toBeInTheDocument();
  expect(
    fetcher.mock.calls.some(([path]) => /checkout|payments/.test(path)),
  ).toBe(false);
});
it('renders the Host inbox using only returned safe details', async () => {
  const fetcher = mockWorkflow((path) =>
    path.includes('/host/bookings?') ? json([booking]) : undefined,
  );
  renderPage(<BookingsPage host />);
  expect(
    await screen.findByText('Requested by Demo Owner'),
  ).toBeInTheDocument();
  expect(screen.getByText('Milo (Dog)')).toBeInTheDocument();
  expect(
    screen.getByRole('link', { name: booking.listing.title }),
  ).toHaveAttribute('href', '/host/bookings/booking-id');
  expect(
    fetcher.mock.calls.some(([path]) => path.includes('/host/bookings?')),
  ).toBe(true);
});
it.each(['accept', 'decline'] as const)(
  'Host %s uses explicit action and refreshes detail and collections',
  async (name) => {
    let status: BookingStatus = 'REQUESTED';
    const fetcher = mockWorkflow((path, init) => {
      if (path.endsWith(`/${name}`) && init?.method === 'POST') {
        status = name === 'accept' ? 'AWAITING_PAYMENT' : 'DECLINED';
        return json({ ...booking, status });
      }
      if (path.endsWith('/host/bookings/booking-id'))
        return json({ ...booking, status });
    });
    const { client } = detail(true);
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    expect(
      await screen.findByText('Requested by Demo Owner'),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', {
        name: name === 'accept' ? 'Accept request' : 'Decline request',
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: 'Accept request' }),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getAllByText(
        name === 'accept' ? 'Payment required' : 'Declined by host',
      ).length,
    ).toBeGreaterThan(0);
    expect(
      JSON.parse(
        fetcher.mock.calls.find(([path]) => path.endsWith(`/${name}`))![1].body,
      ),
    ).toEqual({});
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['bookings'] });
  },
);
it.each([
  'booking_capacity_unavailable',
  'booking_busy',
  'booking_invalid_state',
])('Host acceptance handles %s without pretending success', async (code) => {
  mockWorkflow((path, init) =>
    init?.method === 'POST' && path.endsWith('/accept')
      ? json({ error: { code, message: 'Conflict' } }, 409)
      : path.endsWith('/host/bookings/booking-id')
        ? json(booking)
        : undefined,
  );
  detail(true);
  fireEvent.click(
    await screen.findByRole('button', { name: 'Accept request' }),
  );
  const text =
    code === 'booking_capacity_unavailable'
      ? 'Those dates are no longer available'
      : code === 'booking_busy'
        ? 'being updated'
        : 'has changed';
  expect(await screen.findByRole('alert')).toHaveTextContent(text);
  expect(
    screen.getByText('Waiting for host', { selector: 'span' }),
  ).toBeInTheDocument();
});
it('refreshes detail manually without polling', async () => {
  let accepted = false;
  const fetcher = mockWorkflow((path) =>
    path.endsWith('/bookings/booking-id')
      ? json({
          ...booking,
          status: accepted ? 'AWAITING_PAYMENT' : 'REQUESTED',
        })
      : undefined,
  );
  detail();
  await screen.findByText('Waiting for host');
  accepted = true;
  fireEvent.click(screen.getByRole('button', { name: 'Refresh booking' }));
  await screen.findByRole('heading', { name: 'Payment required' });
  expect(
    fetcher.mock.calls.filter(([path]) =>
      path.endsWith('/bookings/booking-id'),
    ),
  ).toHaveLength(2);
});

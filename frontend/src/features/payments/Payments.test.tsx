import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { CheckoutPage } from './CheckoutPage';
import { PaymentReturnPage } from './PaymentReturnPage';
import { BookingDetailPage } from '../bookings/BookingDetailPage';
import { Header } from '../../components/Header';
import { renderPage } from '../../test/render';
import { booking, mockWorkflow } from '../../test/workflow';
import { json } from '../../test/fixtures';
import type { Booking, BookingStatus } from '../bookings/api';
import { statusLabels } from '../bookings/status';
import * as stripeConfig from './stripe';
import type { Stripe } from '@stripe/stripe-js';

const stripe = vi.hoisted(() => ({
  confirm: vi.fn(),
  provider: vi.fn(),
  state: 'success',
  canConfirm: true,
  amount: 11440,
}));
vi.mock('@stripe/react-stripe-js/checkout', () => ({
  CheckoutElementsProvider: ({
    children,
    options,
  }: PropsWithChildren<{ options: unknown }>) => {
    stripe.provider(options);
    return <>{children}</>;
  },
  PaymentElement: () => (
    <div data-testid="payment-element">Stripe payment iframe boundary</div>
  ),
  ContactDetailsElement: () => <div>Stripe contact iframe boundary</div>,
  useCheckoutElements: () =>
    stripe.state === 'loading'
      ? { type: 'loading' }
      : stripe.state === 'error'
        ? { type: 'error', error: { message: 'Untrusted provider detail' } }
        : {
            type: 'success',
            checkout: {
              currency: 'aud',
              minorUnitsAmountDivisor: 100,
              canConfirm: stripe.canConfirm,
              total: {
                total: { amount: 'A$114.40', minorUnitsAmount: stripe.amount },
              },
              confirm: stripe.confirm,
            },
          },
}));
const payable: Booking = {
  ...booking,
  status: 'AWAITING_PAYMENT',
  payment_expires_at: '2029-11-01T12:00:00Z',
};
// Deliberately not a real Stripe credential or card number.
const syntheticSecret = 'synthetic-runtime-only-checkout-value';
const checkoutResponse = () =>
  json({
    payment_attempt_id: 'attempt-id',
    client_secret: syntheticSecret,
    expires_at: payable.payment_expires_at,
  });
function paymentAPI(current: () => Booking = () => payable) {
  return mockWorkflow((path) =>
    path.endsWith('/checkout-session')
      ? checkoutResponse()
      : path.endsWith('/bookings/booking-id')
        ? json(current())
        : undefined,
  );
}
function payPage(element = <CheckoutPage />) {
  return renderPage(element, {
    path: '/account/bookings/booking-id/pay',
    route: '/account/bookings/:bookingId/pay',
  });
}
function returnPage() {
  return renderPage(<PaymentReturnPage />, {
    path: '/account/bookings/booking-id/payment-return?success=true',
    route: '/account/bookings/:bookingId/payment-return',
  });
}
async function openForm() {
  fireEvent.click(
    await screen.findByRole('button', { name: 'Load secure payment form' }),
  );
  await screen.findByTestId('payment-element');
}
beforeEach(() => {
  stripe.state = 'success';
  stripe.canConfirm = true;
  stripe.amount = 11440;
  stripe.confirm
    .mockReset()
    .mockResolvedValue({ type: 'success', session: {} });
  stripe.provider.mockClear();
  vi.stubEnv('VITE_STRIPE_PUBLISHABLE_KEY', 'pk_test_synthetic');
  vi.spyOn(stripeConfig, 'getStripe').mockResolvedValue({} as Stripe);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});
it('exposes Pay securely only on the Owner awaiting-payment detail', async () => {
  paymentAPI();
  renderPage(<BookingDetailPage />, {
    path: '/account/bookings/booking-id',
    route: '/account/bookings/:bookingId',
  });
  expect(
    await screen.findByRole('link', { name: 'Pay securely' }),
  ).toHaveAttribute('href', '/account/bookings/booking-id/pay');
});
it.each<BookingStatus>([
  'REQUESTED',
  'CONFIRMED',
  'CANCELLED',
  'EXPIRED',
  'DECLINED',
  'PAYMENT_FAILED',
  'COMPLETED',
])('has no payment action for %s', async (status) => {
  paymentAPI(() => ({ ...payable, status }));
  renderPage(<BookingDetailPage />, {
    path: '/account/bookings/booking-id',
    route: '/account/bookings/:bookingId',
  });
  await screen.findByRole('heading', { name: payable.listing.title });
  expect(
    screen.queryByRole('link', { name: 'Pay securely' }),
  ).not.toBeInTheDocument();
});
it('never gives Hosts payment controls or Checkout credentials', async () => {
  const fetcher = mockWorkflow((path) =>
    path.endsWith('/host/bookings/booking-id') ? json(payable) : undefined,
  );
  renderPage(<BookingDetailPage host />, {
    path: '/host/bookings/booking-id',
    route: '/host/bookings/:bookingId',
  });
  await screen.findByRole('heading', { name: 'Payment required' });
  expect(
    screen.queryByRole('link', { name: 'Pay securely' }),
  ).not.toBeInTheDocument();
  expect(
    fetcher.mock.calls.some(([path]) => path.endsWith('/checkout-session')),
  ).toBe(false);
});
it('starts the real empty-body CSRF endpoint without caching/persisting its secret', async () => {
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  const indexed = vi.fn();
  vi.stubGlobal('indexedDB', { open: indexed });
  const fetcher = paymentAPI();
  const { client } = payPage();
  await openForm();
  const call = fetcher.mock.calls.find(([path]) =>
    path.endsWith('/checkout-session'),
  )!;
  expect(call[0]).toBe('/api/v1/bookings/booking-id/checkout-session');
  expect(call[1]).toMatchObject({
    method: 'POST',
    credentials: 'include',
    body: '{}',
    headers: { 'X-CSRF-Token': 'nonce', 'X-PAWTEL-Request': '1' },
  });
  expect(stripe.provider).toHaveBeenCalledWith(
    expect.objectContaining({ clientSecret: syntheticSecret }),
  );
  expect(
    JSON.stringify(
      client
        .getQueryCache()
        .getAll()
        .map((q) => q.state.data),
    ),
  ).not.toContain(syntheticSecret);
  expect(client.getMutationCache().getAll()).toHaveLength(0);
  expect(storage).not.toHaveBeenCalled();
  expect(indexed).not.toHaveBeenCalled();
  expect(screen.queryByText(syntheticSecret)).not.toBeInTheDocument();
  expect(screen.getByLabelText('Current location')).not.toHaveTextContent(
    syntheticSecret,
  );
  expect(screen.getByText('$104 AUD')).toBeInTheDocument();
  expect(screen.getByText('$10.40 AUD')).toBeInTheDocument();
});
it('handles missing public-key configuration before starting a Session', async () => {
  vi.stubEnv('VITE_STRIPE_PUBLISHABLE_KEY', '');
  const fetcher = paymentAPI();
  payPage();
  expect(
    await screen.findByText(/Sandbox payment is not configured/),
  ).toBeInTheDocument();
  expect(
    fetcher.mock.calls.some(([path]) => path.endsWith('/checkout-session')),
  ).toBe(false);
});
it('does not open an expired payment window or invent an EXPIRED state', async () => {
  const fetcher = paymentAPI(() => ({
    ...payable,
    payment_expires_at: '2020-01-01T00:00:00Z',
  }));
  payPage();
  await screen.findByText(/payment window appears closed/);
  expect(screen.getByText('Payment required')).toBeInTheDocument();
  expect(
    fetcher.mock.calls.some(([path]) => path.endsWith('/checkout-session')),
  ).toBe(false);
});
it('refuses non-payable checkout routes using the backend status', async () => {
  const fetcher = paymentAPI(() => ({ ...payable, status: 'CANCELLED' }));
  payPage();
  await screen.findByText('This Booking is not awaiting payment');
  expect(
    fetcher.mock.calls.some(([path]) => path.endsWith('/checkout-session')),
  ).toBe(false);
});
it('handles a foreign/private Booking 404 without starting Stripe', async () => {
  const fetcher = mockWorkflow((path) =>
    path.endsWith('/bookings/booking-id')
      ? json(
          {
            error: { code: 'booking_not_found', message: 'Booking not found.' },
          },
          404,
        )
      : undefined,
  );
  payPage();
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'does not belong to your account',
  );
  expect(
    fetcher.mock.calls.some(([path]) => path.endsWith('/checkout-session')),
  ).toBe(false);
});
it.each([
  'payment_window_closed',
  'booking_not_payable',
  'payment_reconciliation_required',
])('shows checkout rejection %s and does not mount Elements', async (code) => {
  mockWorkflow((path) =>
    path.endsWith('/checkout-session')
      ? json({ error: { code, message: 'Not payable' } }, 409)
      : path.endsWith('/bookings/booking-id')
        ? json(payable)
        : undefined,
  );
  payPage();
  fireEvent.click(
    await screen.findByRole('button', { name: 'Load secure payment form' }),
  );
  await screen.findByRole('alert');
  expect(
    screen.queryByRole('button', { name: 'Load secure payment form' }),
  ).not.toBeInTheDocument();
  expect(stripe.provider).not.toHaveBeenCalled();
});
it('keeps a declined payment retryable within the same Checkout Session', async () => {
  stripe.confirm.mockResolvedValueOnce({
    type: 'error',
    error: {
      code: 'paymentFailed',
      paymentFailed: { declineCode: 'generic_decline' },
    },
  });
  const fetcher = paymentAPI();
  payPage();
  await openForm();
  fireEvent.click(screen.getByRole('button', { name: 'Pay securely' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('declined');
  expect(screen.getByRole('button', { name: 'Pay securely' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Pay securely' }));
  await screen.findAllByText('/account/bookings/booking-id/payment-return');
  expect(
    fetcher.mock.calls.filter(([path]) => path.endsWith('/checkout-session')),
  ).toHaveLength(1);
  expect(stripe.confirm).toHaveBeenCalledWith({
    redirect: 'if_required',
    returnUrl: new URL(
      '/account/bookings/booking-id/payment-return',
      window.location.origin,
    ).href,
  });
});
it('does not locally confirm a Booking after Stripe succeeds', async () => {
  paymentAPI();
  const { client } = payPage();
  await openForm();
  fireEvent.click(screen.getByRole('button', { name: 'Pay securely' }));
  await screen.findAllByText('/account/bookings/booking-id/payment-return');
  const data = client
    .getQueryCache()
    .getAll()
    .map((q) => q.state.data);
  expect(JSON.stringify(data)).not.toContain('CONFIRMED');
});
it('blocks confirmation if Stripe and PAWTEL totals disagree', async () => {
  stripe.amount = 1;
  paymentAPI();
  payPage();
  await openForm();
  expect(screen.getByRole('alert')).toHaveTextContent(
    'total could not be verified',
  );
  expect(screen.getByRole('button', { name: 'Pay securely' })).toBeDisabled();
  expect(stripe.confirm).not.toHaveBeenCalled();
});
it('handles Stripe loading and initialization errors without printing provider payloads', async () => {
  stripe.state = 'loading';
  paymentAPI();
  payPage();
  fireEvent.click(
    await screen.findByRole('button', { name: 'Load secure payment form' }),
  );
  await screen.findByText('Loading secure payment form…');
  stripe.state = 'error';
  fireEvent.click(
    screen.getByRole('button', { name: 'Refresh Booking status' }),
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'could not initialize',
  );
  expect(
    screen.queryByText('Untrusted provider detail'),
  ).not.toBeInTheDocument();
});
it('handles Stripe.js loading rejection and allows a form reload', async () => {
  vi.mocked(stripeConfig.getStripe).mockRejectedValue(
    new Error('synthetic private provider detail'),
  );
  paymentAPI();
  payPage();
  fireEvent.click(
    await screen.findByRole('button', { name: 'Load secure payment form' }),
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Stripe could not load',
  );
  expect(
    screen.getByRole('button', { name: 'Reload secure form' }),
  ).toBeEnabled();
});
it('removes a mounted form when cancellation is observed and does not reopen it', async () => {
  let current = payable;
  const fetcher = paymentAPI(() => current);
  payPage();
  await openForm();
  current = { ...payable, status: 'CANCELLED' };
  fireEvent.click(
    screen.getByRole('button', { name: 'Refresh Booking status' }),
  );
  await screen.findByText('This Booking is not awaiting payment');
  expect(screen.queryByTestId('payment-element')).not.toBeInTheDocument();
  expect(
    fetcher.mock.calls.filter(([path]) => path.endsWith('/checkout-session')),
  ).toHaveLength(1);
});
it('logout unmounts Elements and leaves no private checkout cache', async () => {
  const fetcher = mockWorkflow((path) =>
    path.endsWith('/auth/logout')
      ? new Response(null, { status: 204 })
      : path.endsWith('/checkout-session')
        ? checkoutResponse()
        : path.endsWith('/bookings/booking-id')
          ? json(payable)
          : undefined,
  );
  const { client } = payPage(
    <>
      <Header />
      <CheckoutPage />
    </>,
  );
  await openForm();
  fireEvent.click(screen.getByRole('button', { name: 'Account menu' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Log out' }));
  await waitFor(() =>
    expect(screen.queryByTestId('payment-element')).not.toBeInTheDocument(),
  );
  expect(
    client
      .getQueryCache()
      .getAll()
      .some((q) =>
        JSON.stringify(q.state.data ?? null).includes(syntheticSecret),
      ),
  ).toBe(false);
  expect(
    fetcher.mock.calls.some(([path]) => path.endsWith('/auth/logout')),
  ).toBe(true);
});
it.each<BookingStatus>([
  'CONFIRMED',
  'AWAITING_PAYMENT',
  'EXPIRED',
  'CANCELLED',
  'PAYMENT_FAILED',
])('return uses backend %s despite success=true', async (status) => {
  paymentAPI(() => ({ ...payable, status }));
  returnPage();
  const expected =
    status === 'CONFIRMED'
      ? 'Your stay is confirmed'
      : status === 'AWAITING_PAYMENT'
        ? 'Waiting for payment confirmation'
        : 'Booking status';
  expect(
    await screen.findByRole('heading', { name: expected }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(statusLabels[status], { selector: 'span' }),
  ).toBeInTheDocument();
  if (status !== 'CONFIRMED')
    expect(
      screen.queryByText('Your stay is confirmed'),
    ).not.toBeInTheDocument();
  if (status === 'CANCELLED')
    expect(
      screen.getByText(/flags the payment for reconciliation/),
    ).toBeInTheDocument();
});
it('bounds pending return refetching and still permits manual refresh', async () => {
  vi.useFakeTimers();
  const fetcher = paymentAPI();
  returnPage();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  for (let i = 0; i < 12; i++)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
  const count = () =>
    fetcher.mock.calls.filter(([path]) => path.endsWith('/bookings/booking-id'))
      .length;
  expect(count()).toBeLessThanOrEqual(10);
  expect(count()).toBeGreaterThan(1);
  const stopped = count();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(60_000);
  });
  expect(count()).toBe(stopped);
  fireEvent.click(
    screen.getByRole('button', { name: 'Refresh payment status' }),
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  expect(count()).toBe(stopped + 1);
});
it('stops return refetching on backend confirmation', async () => {
  vi.useFakeTimers();
  let reads = 0;
  const fetcher = paymentAPI(() => ({
    ...payable,
    status: ++reads > 1 ? 'CONFIRMED' : 'AWAITING_PAYMENT',
  }));
  returnPage();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  for (let i = 0; i < 3; i++)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
  expect(
    screen.getByRole('heading', { name: 'Your stay is confirmed' }),
  ).toBeInTheDocument();
  const count = fetcher.mock.calls.length;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(30_000);
  });
  expect(fetcher.mock.calls).toHaveLength(count);
});
it('handles a generic legacy return without guessing a Booking from provider parameters', async () => {
  paymentAPI();
  renderPage(<PaymentReturnPage />, {
    path: '/checkout/return?success=true&session_id=synthetic',
  });
  expect(
    await screen.findByRole('link', { name: 'My Bookings' }),
  ).toHaveAttribute('href', '/account/bookings');
  expect(screen.queryByText('Your stay is confirmed')).not.toBeInTheDocument();
});
it('ignores a late checkout response after logout', async () => {
  let resolve!: (response: Response) => void;
  const pending = new Promise<Response>((done) => {
    resolve = done;
  });
  const fetcher = mockWorkflow((path) =>
    path.endsWith('/auth/logout')
      ? new Response(null, { status: 204 })
      : path.endsWith('/bookings/booking-id')
        ? json(payable)
        : undefined,
  );
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation((path: string, init?: RequestInit) =>
    path.endsWith('/checkout-session') ? pending : original(path, init),
  );
  payPage(
    <>
      <Header />
      <CheckoutPage />
    </>,
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Load secure payment form' }),
  );
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([path]) => path.endsWith('/checkout-session')),
    ).toBe(true),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Account menu' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Log out' }));
  await waitFor(() =>
    expect(
      screen.queryByRole('heading', { name: 'Pay for your stay' }),
    ).not.toBeInTheDocument(),
  );
  const readsAfterLogout = fetcher.mock.calls.filter(([path]) =>
    path.endsWith('/bookings/booking-id'),
  ).length;
  await act(async () => {
    resolve(checkoutResponse());
    await pending;
  });
  expect(stripe.provider).not.toHaveBeenCalled();
  expect(
    fetcher.mock.calls.filter(([path]) =>
      path.endsWith('/bookings/booking-id'),
    ),
  ).toHaveLength(readsAfterLogout);
});
it('rechecks cancellation immediately before Stripe confirmation', async () => {
  let current = payable;
  paymentAPI(() => current);
  payPage();
  await openForm();
  current = { ...payable, status: 'CANCELLED' };
  fireEvent.click(screen.getByRole('button', { name: 'Pay securely' }));
  await screen.findByText('This Booking is not awaiting payment');
  expect(stripe.confirm).not.toHaveBeenCalled();
});

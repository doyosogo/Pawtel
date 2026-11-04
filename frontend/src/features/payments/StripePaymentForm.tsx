import {
  Component,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useNavigate } from 'react-router';
import {
  CheckoutElementsProvider,
  ContactDetailsElement,
  PaymentElement,
  useCheckoutElements,
} from '@stripe/react-stripe-js/checkout';
import type { Stripe } from '@stripe/stripe-js';
import type { Booking } from '../bookings/api';
import { getStripe } from './stripe';
import { paymentReturnPath } from './api';

class ProviderBoundary extends Component<
  { children: ReactNode; retry: () => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div role="alert">
        <p>Secure payment could not initialize.</p>
        <button className="button secondary" onClick={this.props.retry}>
          Reload secure form
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
function PaymentForm({
  booking,
  verifyBooking,
  retry,
}: {
  booking: Booking;
  verifyBooking: () => Promise<boolean>;
  retry: () => void;
}) {
  const state = useCheckoutElements();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState('');
  const [elementFailed, setElementFailed] = useState(false);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  if (state.type === 'loading')
    return <p role="status">Loading secure payment form…</p>;
  if (state.type === 'error' || elementFailed)
    return (
      <div role="alert">
        <p>
          Secure payment could not initialize. Refresh your Booking status
          before trying again.
        </p>
        <button className="button secondary" onClick={retry}>
          Reload secure form
        </button>
      </div>
    );
  const { checkout } = state;
  const matches =
    checkout.currency === 'aud' &&
    checkout.total.total.minorUnitsAmount === booking.total_cents &&
    checkout.minorUnitsAmountDivisor === 100;
  async function submit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !checkout.canConfirm || !matches) return;
    setBusy(true);
    setFailure('');
    try {
      if (!(await verifyBooking()) || !active.current) return;
      const path = paymentReturnPath(booking.id);
      const result = await checkout.confirm({
        redirect: 'if_required',
        returnUrl: new URL(path, window.location.origin).href,
      });
      if (!active.current) return;
      if (result.type === 'error') {
        // Only display our own safe copy; provider exceptions/payloads are not logged.
        setFailure(
          result.error.code === 'paymentFailed'
            ? 'Your payment was declined. Check your details or try another card while this payment window is open.'
            : 'Payment could not be completed. Check the secure form and try again, or check your Booking status.',
        );
      } else {
        // Stripe's result is not PAWTEL Booking authority. Read the backend next.
        navigate(path, { replace: true });
      }
    } catch {
      if (active.current)
        setFailure(
          'We could not check the payment outcome. Check your Booking status before retrying.',
        );
    } finally {
      if (active.current) setBusy(false);
    }
  }
  return (
    <form className="stack" onSubmit={submit}>
      <p>
        Stripe checkout total: <strong>{checkout.total.total.amount}</strong>
      </p>
      {!matches && (
        <p role="alert" className="error-text">
          The payment total could not be verified against your Booking. Return
          to your Booking before paying.
        </p>
      )}
      <ContactDetailsElement />
      <PaymentElement
        options={{ layout: 'accordion' }}
        onLoadError={() => setElementFailed(true)}
      />
      {failure && (
        <p className="error-text" role="alert">
          {failure}
        </p>
      )}
      <button
        className="button"
        type="submit"
        disabled={busy || !checkout.canConfirm || !matches}
      >
        {busy ? 'Checking payment…' : 'Pay securely'}
      </button>
      <p className="field-help">
        Payment details are collected securely by Stripe. A declined attempt
        does not cancel your Booking.
      </p>
    </form>
  );
}
export function StripePaymentForm({
  clientSecret,
  booking,
  verifyBooking,
  retry,
}: {
  clientSecret: string;
  booking: Booking;
  verifyBooking: () => Promise<boolean>;
  retry: () => void;
}) {
  const [stripe, setStripe] = useState<Stripe | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    void getStripe().then(
      (value) => {
        if (active) {
          if (value) setStripe(value);
          else setFailed(true);
        }
      },
      () => {
        if (active) setFailed(true);
      },
    );
    return () => {
      active = false;
    };
  }, []);
  const options = useMemo(
    () => ({
      clientSecret,
      elementsOptions: {
        appearance: {
          theme: 'stripe' as const,
          variables: {
            colorPrimary: '#6545b6',
            colorText: '#252333',
            colorBackground: '#ffffff',
            colorDanger: '#a5283b',
            borderRadius: '10px',
            fontFamily: 'system-ui, sans-serif',
          },
        },
        loader: 'auto' as const,
      },
    }),
    [clientSecret],
  );
  if (failed)
    return (
      <div role="alert">
        <p>Stripe could not load. Check your connection and try again.</p>
        <button className="button secondary" onClick={retry}>
          Reload secure form
        </button>
      </div>
    );
  if (!stripe) return <p role="status">Loading Stripe…</p>;
  return (
    <ProviderBoundary retry={retry}>
      <CheckoutElementsProvider stripe={stripe} options={options}>
        <PaymentForm
          booking={booking}
          verifyBooking={verifyBooking}
          retry={retry}
        />
      </CheckoutElementsProvider>
    </ProviderBoundary>
  );
}

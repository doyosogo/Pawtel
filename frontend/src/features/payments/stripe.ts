import { loadStripe } from '@stripe/stripe-js/pure';
import type { Stripe } from '@stripe/stripe-js';
export function publishableKey() {
  const key = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY?.trim();
  // PAWTEL's backend intentionally accepts sandbox/test keys only.
  return key?.startsWith('pk_test_') ? key : null;
}
let stripePromise: Promise<Stripe | null> | undefined;
export function getStripe() {
  const key = publishableKey();
  if (!key)
    return Promise.reject(new Error('Sandbox payments are not configured.'));
  stripePromise ??= loadStripe(key).catch(() => {
    stripePromise = undefined;
    throw new Error('Secure payment could not load.');
  });
  return stripePromise;
}

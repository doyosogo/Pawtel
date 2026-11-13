import { lazy, Suspense } from 'react';
import { ShowcaseCheckout } from '../../showcase/ShowcasePages';
// Inline Vite constants let the bundler eliminate the Stripe import entirely in showcase output.
const Checkout =
  import.meta.env.MODE === 'showcase' &&
  import.meta.env.VITE_PAWTEL_SHOWCASE === 'true'
    ? ShowcaseCheckout
    : lazy(() =>
        import('./CheckoutPage').then((module) => ({
          default: module.CheckoutPage,
        })),
      );
export function CheckoutRoute() {
  return (
    <Suspense fallback={<p role="status">Loading checkout…</p>}>
      <Checkout />
    </Suspense>
  );
}

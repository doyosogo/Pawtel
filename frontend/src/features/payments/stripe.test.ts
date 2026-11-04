import { afterEach, expect, it, vi } from 'vitest';
import { publishableKey } from './stripe';
afterEach(() => vi.unstubAllEnvs());
it.each(['', 'sk_test_not_a_public_key', 'pk_live_not_supported'])(
  'rejects missing or unsafe browser configuration %s',
  (value) => {
    vi.stubEnv('VITE_STRIPE_PUBLISHABLE_KEY', value);
    expect(publishableKey()).toBeNull();
  },
);
it('accepts only the explicitly public test key variable', () => {
  vi.stubEnv('VITE_STRIPE_PUBLISHABLE_KEY', ' pk_test_synthetic ');
  expect(publishableKey()).toBe('pk_test_synthetic');
});

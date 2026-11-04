import { vi } from 'vitest';
import { json, user, listing, anonymous } from './fixtures';
import type { Pet } from '../features/pets/api';
import type { Booking } from '../features/bookings/api';
export const verifiedUser = {
  ...user,
  email_verified_at: '2026-01-01T00:00:00Z',
};
export const dog: Pet = {
  id: 'dog-id',
  name: 'Milo',
  species: 'DOG',
  breed: null,
  date_of_birth: null,
  is_active: true,
  created_at: '',
  updated_at: '',
};
export const cat: Pet = { ...dog, id: 'cat-id', name: 'Luna', species: 'CAT' };
export const booking: Booking = {
  id: 'booking-id',
  listing: {
    id: listing.id,
    title: listing.title,
    suburb: listing.suburb,
    state: listing.state,
  },
  pets: [dog],
  owner_display_name: 'Demo Owner',
  check_in: '2029-11-10',
  check_out: '2029-11-12',
  status: 'REQUESTED',
  nightly_base_price_cents: 5200,
  additional_pet_price_cents: 1500,
  subtotal_cents: 10400,
  service_fee_cents: 1040,
  total_cents: 11440,
  payment_expires_at: null,
  created_at: '',
  updated_at: '',
};
export function mockWorkflow(
  handler: (path: string, init?: RequestInit) => Response | undefined = () =>
    undefined,
) {
  const fetcher = vi
    .fn()
    .mockImplementation((path: string, init?: RequestInit) => {
      const response = handler(path, init);
      if (response) return Promise.resolve(response);
      if (path.endsWith('/auth/me')) return Promise.resolve(json(verifiedUser));
      if (path.endsWith('/auth/csrf'))
        return Promise.resolve(json({ csrf_token: 'nonce' }));
      if (path.includes('/pets')) return Promise.resolve(json([dog, cat]));
      if (path.endsWith('/host/profile'))
        return Promise.resolve(
          json({
            user_id: user.id,
            bio: 'Host',
            created_at: '',
            updated_at: '',
          }),
        );
      if (path.includes('/listings/')) return Promise.resolve(json(listing));
      return Promise.resolve(anonymous());
    });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

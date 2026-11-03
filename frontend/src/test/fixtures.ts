import type { Listing } from '../features/listings/api';
export const listing: Listing = {
  id: '11111111-1111-4111-8111-111111111111',
  title: 'A sunny home by the coast',
  description: 'A fictional coastal home.',
  suburb: 'Glenelg',
  state: 'SA',
  postcode: '5045',
  country_code: 'AU',
  base_nightly_price_cents: 5200,
  additional_pet_price_cents: 1500,
  max_pet_capacity: 3,
  accepted_species: ['DOG', 'CAT'],
  host: { display_name: 'Riley', bio: 'A fictional host bio.' },
};
export const user = {
  id: '22222222-2222-4222-8222-222222222222',
  display_name: 'Alex',
  email: 'alex@example.test',
  email_verified_at: null,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
};
export function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
export const anonymous = () =>
  json(
    {
      error: {
        code: 'authentication_required',
        message: 'Authentication is required.',
      },
    },
    401,
  );
export const page = (items = [listing]) => ({
  items,
  limit: 8,
  offset: 0,
  has_more: false,
  next_offset: null,
});

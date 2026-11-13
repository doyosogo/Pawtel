import type { User } from '../features/auth/session';
import type { HostListing } from '../features/host/api';
import type { Pet } from '../features/pets/api';
import type { Booking } from '../features/bookings/api';
const timestamp = '2026-01-01T00:00:00Z';
export const owner: User = {
  id: 'showcase-owner',
  display_name: 'Demo Owner',
  email: 'owner@showcase.example.com',
  email_verified_at: timestamp,
  is_active: true,
  created_at: timestamp,
};
export const host: User = {
  ...owner,
  id: 'showcase-host',
  display_name: 'Demo Host',
  email: 'host@showcase.example.com',
};
export function fixtures() {
  const places = [
    ['Glenelg', 'SA', '5045', 'Coastal calm for little companions', 'coastal'],
    ['Norwood', 'SA', '5067', 'A sunny courtyard retreat', 'courtyard'],
    ['Unley', 'SA', '5061', 'Garden days and cosy evenings', 'garden'],
    ['Prospect', 'SA', '5082', 'A bright sunroom hideaway', 'sunroom'],
    ['Adelaide', 'SA', '5000', 'City terrace with a gentle pace', 'terrace'],
    ['Stirling', 'SA', '5152', 'A cottage escape in the hills', 'cottage'],
    ['Semaphore', 'SA', '5019', 'Seaside stays with room to relax', 'coastal'],
    ['Goodwood', 'SA', '5034', 'A welcoming garden home', 'garden'],
    ['Henley Beach', 'SA', '5022', 'Sunny afternoons by the coast', 'sunroom'],
    ['Richmond', 'VIC', '3121', 'A quiet Melbourne courtyard', 'courtyard'],
    ['Newtown', 'NSW', '2042', 'A cosy Sydney terrace', 'terrace'],
    ['Paddington', 'QLD', '4064', 'A breezy Brisbane cottage', 'cottage'],
  ];
  const listings: (HostListing & {
    host: { display_name: string; bio: string };
    hostId: string;
  })[] = places.map(([suburb, state, postcode, title, image], i) => ({
    id: `showcase-stay-${i + 1}`,
    title,
    suburb,
    state,
    postcode,
    country_code: 'AU',
    description: `Settle into a slower rhythm in ${suburb}. This fictional boarding home offers a comfortable place for your pet while you are away. Meet your synthetic Host, explore the stay details and try a simulated request. All descriptions and illustrations are demonstration content.`,
    base_nightly_price_cents: 4800 + i * 500,
    additional_pet_price_cents: 1800,
    max_pet_capacity: (i % 3) + 2,
    accepted_species:
      i % 3 === 1 ? ['CAT'] : i % 3 === 2 ? ['DOG'] : ['DOG', 'CAT'],
    status: 'PUBLISHED',
    created_at: timestamp,
    updated_at: timestamp,
    hostId: i < 3 ? host.id : `fictional-host-${i}`,
    host: {
      display_name:
        i < 3 ? host.display_name : ['Riley', 'Jordan', 'Casey'][i % 3],
      bio: 'A fictional animal lover opening their home for a synthetic showcase stay.',
    },
    images: [0, 1].map((n) => ({
      id: `image-${i}-${n}`,
      url: `/media/${n ? 'garden' : image}.svg`,
      alt_text: `Fictional ${suburb} stay illustration${n ? ', garden view' : ''}`,
      sort_order: n,
    })),
  }));
  const pets: (Pet & { ownerId: string })[] = [
    {
      id: 'showcase-dog',
      name: 'Milo',
      species: 'DOG',
      breed: 'Cavoodle',
      date_of_birth: '2022-05-12',
      is_active: true,
      created_at: timestamp,
      updated_at: timestamp,
      ownerId: owner.id,
    },
    {
      id: 'showcase-cat',
      name: 'Luna',
      species: 'CAT',
      breed: null,
      date_of_birth: '2021-09-20',
      is_active: true,
      created_at: timestamp,
      updated_at: timestamp,
      ownerId: owner.id,
    },
  ];
  const start = new Date();
  start.setUTCDate(start.getUTCDate() + 30);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 3);
  const bookings: (Booking & { ownerId: string; hostId: string })[] = (
    ['REQUESTED', 'AWAITING_PAYMENT', 'CONFIRMED', 'DECLINED'] as const
  ).map((status, i) => ({
    id: `showcase-booking-${i + 1}`,
    listing: listings[0],
    pets: [pets[0]],
    owner_display_name: owner.display_name,
    ownerId: owner.id,
    hostId: host.id,
    check_in: start.toISOString().slice(0, 10),
    check_out: end.toISOString().slice(0, 10),
    status,
    nightly_base_price_cents: 4800,
    additional_pet_price_cents: 1800,
    subtotal_cents: 14400,
    service_fee_cents: 1440,
    total_cents: 15840,
    payment_expires_at:
      status === 'AWAITING_PAYMENT'
        ? new Date(Date.now() + 86400000).toISOString()
        : null,
    created_at: timestamp,
    updated_at: timestamp,
  }));
  return { listings, pets, bookings };
}

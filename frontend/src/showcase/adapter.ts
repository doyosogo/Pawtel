import { ApiError } from '../lib/api';
import type { BookingInput } from '../features/bookings/api';
import type { ListingInput } from '../features/host/api';
import type { PetInput } from '../features/pets/api';
import { validStay, localToday } from '../features/listings/search';
import { fixtures, owner, host } from './fixtures';
export type Persona = 'visitor' | 'owner' | 'host';
let persona: Persona = 'visitor';
let data = fixtures();
let sequence = 0;
let hostBio = 'A fictional Host welcoming pets to Adelaide.';
export function currentPersona() {
  return persona;
}
export function setPersona(value: Persona) {
  persona = value;
}
export function resetShowcase() {
  persona = 'visitor';
  hostBio = 'A fictional Host welcoming pets to Adelaide.';
  data = fixtures();
  sequence = 0;
}
function fail(code: string, message: string, status = 400): never {
  throw new ApiError(status, code, message);
}
function user() {
  if (persona === 'visitor')
    fail('authentication_required', 'Choose a showcase persona.', 401);
  return persona === 'owner' ? owner : host;
}
function hostOnly() {
  if (user().id !== host.id)
    fail(
      'host_profile_required',
      'Explore as Host to use this workspace.',
      404,
    );
}
const id = () => `showcase-created-${++sequence}`;
const now = () => new Date().toISOString();
// A closed local dispatcher: an unsupported path fails locally, NEVER falls back to fetch.
export async function showcaseRequest<T>(
  path: string,
  method = 'GET',
  input: unknown = {},
): Promise<T> {
  const url = new URL(path, 'https://showcase.invalid');
  const parts = url.pathname.split('/').filter(Boolean);
  const q = url.searchParams;
  const body = input as Record<string, unknown>;
  let result: unknown;
  if (url.pathname === '/config')
    result = { portfolio_demo: false, registration_enabled: false };
  else if (url.pathname === '/auth/me') result = user();
  else if (url.pathname === '/auth/logout') {
    persona = 'visitor';
  } else if (parts[0] === 'auth')
    fail(
      'showcase_only',
      'Use Explore as Owner or Explore as Host; no passwords or tokens exist in this showcase.',
    );
  else if (parts[0] === 'listings') {
    const listing = data.listings.find(
      (l) => l.id === parts[1] && l.status === 'PUBLISHED',
    );
    if (parts[1] && !listing)
      fail('listing_not_found', 'This synthetic stay is not public.', 404);
    if (parts[2] === 'availability' && listing) {
      const count = Number(q.get('pet_count') ?? 1);
      if (!validStay(q.get('check_in') ?? '', q.get('check_out') ?? ''))
        fail('invalid_booking_dates', 'Choose valid stay dates.');
      result = {
        listing_id: listing.id,
        check_in: q.get('check_in'),
        check_out: q.get('check_out'),
        pet_count: count,
        available: count <= listing.max_pet_capacity,
        remaining_capacity_at_tightest_point: listing.max_pet_capacity,
      };
    } else if (listing) result = listing;
    else {
      const items = data.listings.filter(
        (l) =>
          l.status === 'PUBLISHED' &&
          (!q.get('suburb') ||
            l.suburb.toLowerCase().includes(q.get('suburb')!.toLowerCase())) &&
          (!q.get('state') || l.state === q.get('state')) &&
          (!q.get('postcode') || l.postcode === q.get('postcode')) &&
          q
            .getAll('species')
            .every((species) =>
              l.accepted_species.includes(species as 'DOG' | 'CAT'),
            ) &&
          l.max_pet_capacity >= Number(q.get('pet_count') ?? 1) &&
          l.base_nightly_price_cents >= Number(q.get('min_price_cents') ?? 0) &&
          l.base_nightly_price_cents <=
            Number(q.get('max_price_cents') ?? Infinity),
      );
      const offset = Math.max(0, Number(q.get('offset') ?? 0));
      const limit = Math.min(100, Math.max(1, Number(q.get('limit') ?? 8)));
      const has_more = offset + limit < items.length;
      result = {
        items: items.slice(offset, offset + limit),
        limit,
        offset,
        has_more,
        next_offset: has_more ? offset + limit : null,
      };
    }
  } else if (parts[0] === 'pets') {
    const uid = user().id;
    const pet = data.pets.find((p) => p.id === parts[1] && p.ownerId === uid);
    if (parts[1] && !pet)
      fail('pet_not_available', 'Synthetic pet not found.', 404);
    if (method === 'GET')
      result =
        pet ??
        data.pets.filter(
          (p) =>
            p.ownerId === uid &&
            (q.get('include_archived') === 'true' || p.is_active),
        );
    else if (method === 'DELETE' && pet) pet.is_active = false;
    else {
      const values = input as PetInput;
      if (
        !values.name?.trim() ||
        !['DOG', 'CAT'].includes(values.species) ||
        (values.date_of_birth && values.date_of_birth > localToday())
      )
        fail(
          'validation_error',
          'Use a name, Dog or Cat, and a birth date that is not in the future.',
        );
      const fields = {
        name: values.name.trim(),
        species: values.species,
        breed: values.breed,
        date_of_birth: values.date_of_birth,
        updated_at: now(),
      };
      if (pet) {
        Object.assign(pet, fields);
        result = pet;
      } else {
        result = {
          ...fields,
          id: id(),
          ownerId: uid,
          is_active: true,
          created_at: now(),
        };
        data.pets.push(result as (typeof data.pets)[number]);
      }
    }
  } else if (parts[0] === 'host' && parts[1] === 'profile') {
    hostOnly();
    if (method !== 'GET')
      hostBio = typeof body.bio === 'string' ? body.bio : '';
    result = {
      user_id: host.id,
      bio: hostBio,
      created_at: host.created_at,
      updated_at: now(),
    };
  } else if (parts[0] === 'host' && parts[1] === 'listings') {
    hostOnly();
    const listing = data.listings.find(
      (l) => l.id === parts[2] && l.hostId === host.id,
    );
    if (parts[2] && !listing)
      fail('listing_not_found', 'Synthetic Listing not found.', 404);
    if (method === 'GET')
      result =
        listing ??
        data.listings.filter(
          (l) =>
            l.hostId === host.id &&
            (q.get('status')
              ? l.status === q.get('status')
              : l.status !== 'ARCHIVED'),
        );
    else if (listing?.status === 'ARCHIVED')
      fail('listing_archived', 'Archived Listings are read-only.');
    else if (parts[3] === 'images') {
      if (parts[4] === 'order') {
        const ids = body.image_ids as string[];
        if (
          ids.length !== listing!.images!.length ||
          new Set(ids).size !== ids.length ||
          ids.some(
            (value) => !listing!.images!.some((image) => image.id === value),
          )
        )
          fail('image_changed', 'Refresh synthetic images.');
        listing!.images = ids.map((value, index) => ({
          ...listing!.images!.find((image) => image.id === value)!,
          sort_order: index,
        }));
        result = listing!.images;
      } else if (method === 'DELETE') {
        listing!.images = listing!
          .images!.filter((image) => image.id !== parts[4])
          .map((image, index) => ({ ...image, sort_order: index }));
        result = { cleanup_pending: false };
      } else
        fail(
          'showcase_only',
          'Cloud upload is available in the full-stack implementation.',
        );
    } else if (method === 'DELETE' && listing) {
      listing.status = 'ARCHIVED';
    } else {
      const values = input as Partial<ListingInput> & {
        status?: 'DRAFT' | 'PUBLISHED';
      };
      if (
        values.status === 'PUBLISHED' &&
        !(values.accepted_species ?? listing?.accepted_species)?.length
      )
        fail('listing_not_ready', 'Choose at least one species.');
      const allowed = [
        'title',
        'description',
        'suburb',
        'state',
        'postcode',
        'max_pet_capacity',
        'base_nightly_price_cents',
        'additional_pet_price_cents',
        'accepted_species',
        'status',
      ];
      const fields = Object.fromEntries(
        Object.entries(values).filter(([key]) => allowed.includes(key)),
      );
      if (listing) {
        Object.assign(listing, fields, { updated_at: now() });
        result = listing;
      } else {
        const created = {
          ...data.listings[0],
          ...fields,
          id: id(),
          hostId: host.id,
          host: { display_name: host.display_name, bio: 'Synthetic Host' },
          images: [],
          status: 'DRAFT' as const,
          created_at: now(),
          updated_at: now(),
        };
        data.listings.push(created);
        result = created;
      }
    }
  } else if (
    parts[0] === 'bookings' ||
    (parts[0] === 'host' && parts[1] === 'bookings')
  ) {
    const isHost = parts[0] === 'host';
    if (isHost) hostOnly();
    const uid = user().id;
    const bid = parts[isHost ? 2 : 1];
    const action = parts[isHost ? 3 : 2];
    const booking = data.bookings.find(
      (b) => b.id === bid && (isHost ? b.hostId : b.ownerId) === uid,
    );
    if (bid && !booking)
      fail('booking_not_found', 'Synthetic Booking not found.', 404);
    if (method === 'GET')
      result =
        booking ??
        data.bookings
          .filter(
            (b) =>
              (isHost ? b.hostId : b.ownerId) === uid &&
              (!q.get('status') || b.status === q.get('status')),
          )
          .slice(
            Number(q.get('offset') ?? 0),
            Number(q.get('offset') ?? 0) + Number(q.get('limit') ?? 20),
          );
    else if (action && booking) {
      if (action === 'checkout-session')
        fail(
          'showcase_only',
          'Stripe checkout is disabled in the public frontend showcase.',
        );
      if (
        action === 'cancel' &&
        !isHost &&
        ['REQUESTED', 'AWAITING_PAYMENT'].includes(booking.status)
      )
        booking.status = 'CANCELLED';
      else if (
        isHost &&
        booking.status === 'REQUESTED' &&
        ['accept', 'decline'].includes(action)
      ) {
        booking.status = action === 'accept' ? 'AWAITING_PAYMENT' : 'DECLINED';
        booking.payment_expires_at =
          action === 'accept'
            ? new Date(Date.now() + 1800000).toISOString()
            : null;
      } else
        fail('booking_invalid_state', 'This simulated Booking has changed.');
      booking.updated_at = now();
      result = booking;
    } else {
      const values = input as BookingInput;
      const listing = data.listings.find(
        (l) => l.id === values.listing_id && l.status === 'PUBLISHED',
      );
      if (!listing)
        fail('listing_unavailable', 'This synthetic stay is not public.');
      if (listing.hostId === uid)
        fail(
          'self_booking_not_allowed',
          'Explore as Owner to request this stay.',
        );
      if (
        !validStay(values.check_in, values.check_out) ||
        values.check_in < localToday()
      )
        fail('invalid_booking_dates', 'Choose future stay dates.');
      const pets = data.pets.filter(
        (p) =>
          values.pet_ids.includes(p.id) && p.ownerId === uid && p.is_active,
      );
      if (
        !pets.length ||
        pets.length !== values.pet_ids.length ||
        new Set(values.pet_ids).size !== pets.length
      )
        fail('pet_not_available', 'Choose active synthetic pets.');
      if (pets.some((p) => !listing.accepted_species.includes(p.species)))
        fail('pet_not_accepted', 'Choose an accepted species.');
      if (pets.length > listing.max_pet_capacity)
        fail('booking_capacity_unavailable', 'Choose fewer pets.');
      const nights =
        (Date.parse(values.check_out) - Date.parse(values.check_in)) / 86400000;
      const subtotal =
        nights *
        (listing.base_nightly_price_cents +
          (pets.length - 1) * listing.additional_pet_price_cents);
      const fee = Math.round(subtotal / 10);
      const created = {
        id: id(),
        listing,
        pets,
        owner_display_name: user().display_name,
        ownerId: uid,
        hostId: listing.hostId,
        check_in: values.check_in,
        check_out: values.check_out,
        status: 'REQUESTED' as const,
        nightly_base_price_cents: listing.base_nightly_price_cents,
        additional_pet_price_cents: listing.additional_pet_price_cents,
        subtotal_cents: subtotal,
        service_fee_cents: fee,
        total_cents: subtotal + fee,
        payment_expires_at: null,
        created_at: now(),
        updated_at: now(),
      };
      data.bookings.unshift(created);
      result = created;
    }
  } else
    fail(
      'showcase_unavailable',
      'This action is available in the full-stack implementation.',
      404,
    );
  // Components never receive mutable references into adapter state.
  return result === undefined
    ? (undefined as T)
    : (structuredClone(result) as T);
}

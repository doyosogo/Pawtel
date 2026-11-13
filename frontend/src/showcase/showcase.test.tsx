import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import {
  showcaseRequest,
  currentPersona,
  resetShowcase,
  setPersona,
} from './adapter';
import { ShowcaseNotice } from './ShowcaseNotice';
import { ShowcaseCheckout } from './ShowcasePages';
import type { ListingPage } from '../features/listings/api';
import type { Booking } from '../features/bookings/api';
import type { Pet } from '../features/pets/api';
vi.hoisted(() => {
  vi.stubEnv('MODE', 'showcase');
  vi.stubEnv('VITE_PAWTEL_SHOWCASE', 'true');
});
const input = {
  listing_id: 'showcase-stay-1',
  pet_ids: ['showcase-dog'],
  check_in: '2090-01-01',
  check_out: '2090-01-04',
};
beforeEach(() => {
  resetShowcase();
  vi.stubEnv('MODE', 'showcase');
  vi.stubEnv('VITE_PAWTEL_SHOWCASE', 'true');
  vi.stubGlobal(
    'fetch',
    vi.fn(() => {
      throw new Error('Network forbidden');
    }),
  );
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
// Import the mode-dependent entry through a fresh module so compile-time config is evaluated per test.
async function client() {
  vi.resetModules();
  return import('../lib/api');
}
function wrapper(child: React.ReactNode, route = '/') {
  const query = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={query}>
      <MemoryRouter initialEntries={[route]}>{child}</MemoryRouter>
    </QueryClientProvider>,
  );
}
describe('closed in-memory showcase contracts', () => {
  it('starts anonymous and switches verified synthetic personas without credentials', async () => {
    await expect(showcaseRequest('/auth/me')).rejects.toMatchObject({
      status: 401,
    });
    setPersona('owner');
    expect(await showcaseRequest('/auth/me')).toMatchObject({
      display_name: 'Demo Owner',
    });
    setPersona('host');
    expect(await showcaseRequest('/auth/me')).toMatchObject({
      display_name: 'Demo Host',
    });
    await showcaseRequest('/auth/logout', 'POST');
    expect(currentPersona()).toBe('visitor');
    expect(localStorage.length + sessionStorage.length).toBe(0);
  });
  it('filters suburb, postcode, state, all accepted species, capacity, price and pagination', async () => {
    const page = await showcaseRequest<ListingPage>(
      '/listings?suburb=Glenelg&state=SA&postcode=5045&species=DOG&species=CAT&pet_count=2&max_price_cents=5000',
    );
    expect(page.items.map((l) => l.id)).toEqual(['showcase-stay-1']);
    expect(
      (await showcaseRequest<ListingPage>('/listings?pet_count=999')).items,
    ).toEqual([]);
    expect(
      (await showcaseRequest<ListingPage>('/listings?limit=8')).next_offset,
    ).toBe(8);
    expect(
      (await showcaseRequest<ListingPage>('/listings?limit=8&offset=8')).items,
    ).toHaveLength(4);
  });
  it('provides deterministic advisory availability without reserving space', async () => {
    expect(
      await showcaseRequest(
        '/listings/showcase-stay-1/availability?check_in=2090-01-01&check_out=2090-01-04&pet_count=1',
      ),
    ).toMatchObject({ available: true });
    expect(
      await showcaseRequest(
        '/listings/showcase-stay-1/availability?check_in=2090-01-01&check_out=2090-01-04&pet_count=9',
      ),
    ).toMatchObject({ available: false });
  });
  it('simulates request/accept/cancel with a price snapshot and ignores client prices', async () => {
    setPersona('owner');
    const booking = await showcaseRequest<Booking>('/bookings', 'POST', {
      ...input,
      total_cents: 1,
      status: 'CONFIRMED',
    });
    expect(booking).toMatchObject({ status: 'REQUESTED', total_cents: 15840 });
    setPersona('host');
    expect(
      await showcaseRequest(`/host/bookings/${booking.id}/accept`, 'POST'),
    ).toMatchObject({ status: 'AWAITING_PAYMENT' });
    setPersona('owner');
    expect(await showcaseRequest(`/bookings/${booking.id}`)).toMatchObject({
      status: 'AWAITING_PAYMENT',
    });
    expect(
      await showcaseRequest(`/bookings/${booking.id}/cancel`, 'POST'),
    ).toMatchObject({ status: 'CANCELLED' });
  });
  it('declines through the explicit simulated Host action', async () => {
    setPersona('host');
    expect(
      await showcaseRequest(
        '/host/bookings/showcase-booking-1/decline',
        'POST',
      ),
    ).toMatchObject({ status: 'DECLINED' });
    await expect(
      showcaseRequest('/host/bookings/showcase-booking-1/accept', 'POST'),
    ).rejects.toMatchObject({ code: 'booking_invalid_state' });
  });
  it('rejects unsupported species, duplicate pets and invalid dates locally', async () => {
    setPersona('owner');
    await expect(
      showcaseRequest('/bookings', 'POST', {
        ...input,
        listing_id: 'showcase-stay-2',
      }),
    ).rejects.toMatchObject({ code: 'pet_not_accepted' });
    await expect(
      showcaseRequest('/bookings', 'POST', {
        ...input,
        pet_ids: ['showcase-dog', 'showcase-dog'],
      }),
    ).rejects.toMatchObject({ code: 'pet_not_available' });
    await expect(
      showcaseRequest('/bookings', 'POST', {
        ...input,
        check_out: input.check_in,
      }),
    ).rejects.toMatchObject({ code: 'invalid_booking_dates' });
  });
  it('creates, edits and archives only synthetic pets without submitting identity', async () => {
    setPersona('owner');
    const pet = await showcaseRequest<Pet>('/pets', 'POST', {
      name: 'Pip',
      species: 'CAT',
      breed: null,
      date_of_birth: null,
      owner_id: 'foreign',
    });
    expect(pet.name).toBe('Pip');
    await showcaseRequest(`/pets/${pet.id}`, 'PATCH', {
      name: 'Pippa',
      species: 'CAT',
      breed: null,
      date_of_birth: null,
    });
    await showcaseRequest(`/pets/${pet.id}`, 'DELETE');
    expect(
      (await showcaseRequest<Pet[]>('/pets')).some((p) => p.id === pet.id),
    ).toBe(false);
    expect(
      (await showcaseRequest<Pet[]>('/pets?include_archived=true')).find(
        (p) => p.id === pet.id,
      ),
    ).toMatchObject({ name: 'Pippa', is_active: false });
  });
  it('keeps draft Listings private until simulated publication and preserves archive', async () => {
    setPersona('host');
    const listing = await showcaseRequest<{ id: string; status: string }>(
      '/host/listings',
      'POST',
      { title: 'Synthetic draft', accepted_species: [] },
    );
    expect(listing.status).toBe('DRAFT');
    await expect(
      showcaseRequest(`/listings/${listing.id}`),
    ).rejects.toMatchObject({ status: 404 });
    await expect(
      showcaseRequest(`/host/listings/${listing.id}`, 'PATCH', {
        status: 'PUBLISHED',
      }),
    ).rejects.toMatchObject({ code: 'listing_not_ready' });
    await showcaseRequest(`/host/listings/${listing.id}`, 'PATCH', {
      accepted_species: ['DOG'],
      status: 'PUBLISHED',
    });
    expect(await showcaseRequest(`/listings/${listing.id}`)).toMatchObject({
      title: 'Synthetic draft',
    });
    await showcaseRequest(`/host/listings/${listing.id}`, 'DELETE');
    await expect(
      showcaseRequest(`/host/listings/${listing.id}`, 'PATCH', { title: 'No' }),
    ).rejects.toMatchObject({ code: 'listing_archived' });
  });
  it('reorders and removes bundled images without Cloudinary', async () => {
    setPersona('host');
    const images = await showcaseRequest<{ id: string; sort_order: number }[]>(
      '/host/listings/showcase-stay-1/images/order',
      'PATCH',
      { image_ids: ['image-0-1', 'image-0-0'] },
    );
    expect(images[0]).toMatchObject({ id: 'image-0-1', sort_order: 0 });
    expect(
      await showcaseRequest(
        '/host/listings/showcase-stay-1/images/image-0-1',
        'DELETE',
      ),
    ).toEqual({ cleanup_pending: false });
  });
  it('reset restores fixtures and anonymous state', async () => {
    setPersona('host');
    await showcaseRequest('/host/listings/showcase-stay-1', 'DELETE');
    resetShowcase();
    expect(currentPersona()).toBe('visitor');
    expect(await showcaseRequest('/listings/showcase-stay-1')).toBeDefined();
  });
  it('blocks real auth, CSRF, provider checkout and unknown paths without fallback', async () => {
    for (const path of [
      '/auth/login',
      '/auth/register',
      '/auth/csrf',
      '/unknown',
    ])
      await expect(showcaseRequest(path)).rejects.toBeDefined();
    setPersona('owner');
    await expect(
      showcaseRequest('/bookings/showcase-booking-2/checkout-session', 'POST'),
    ).rejects.toMatchObject({ code: 'showcase_only' });
    expect(fetch).not.toHaveBeenCalled();
  });
  it('persona controls update session UI and keep the shared in-memory journey', async () => {
    wrapper(<ShowcaseNotice />);
    fireEvent.click(screen.getByRole('button', { name: 'Explore as Owner' }));
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Explore as Owner' }),
      ).toHaveAttribute('aria-pressed', 'true'),
    );
    expect(currentPersona()).toBe('owner');
    fireEvent.click(screen.getByRole('button', { name: 'Explore as Host' }));
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Explore as Host' }),
      ).toHaveAttribute('aria-pressed', 'true'),
    );
    expect(fetch).not.toHaveBeenCalled();
  });
  it('checkout renders the shared summary and explicit no-card limitation', async () => {
    setPersona('owner');
    wrapper(
      <Routes>
        <Route path="/pay/:bookingId" element={<ShowcaseCheckout />} />
      </Routes>,
      '/pay/showcase-booking-2',
    );
    expect(
      await screen.findByRole('heading', {
        name: 'Stripe checkout is disabled in the public frontend showcase.',
      }),
    ).toBeVisible();
    expect(screen.getByText('Accommodation subtotal')).toBeVisible();
    expect(document.querySelector('iframe')).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });
});
describe('build-mode boundary', () => {
  it('explicit showcase inputs route client reads/writes locally with no CSRF or storage', async () => {
    const api = await client();
    await api.get('/listings');
    await api.write('/auth/logout');
    await expect(
      api.uploadImage(
        'id',
        new File(['x'], 'x.png', { type: 'image/png' }),
        '',
      ),
    ).rejects.toMatchObject({ code: 'showcase_only' });
    expect(fetch).not.toHaveBeenCalled();
    expect(localStorage.length + sessionStorage.length).toBe(0);
  });
  it('ordinary development remains real API mode even if only the flag is supplied', async () => {
    vi.stubEnv('MODE', 'development');
    const api = await client();
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [] })),
    );
    await api.get('/listings');
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/listings',
      expect.objectContaining({ credentials: 'include' }),
    );
  });
  it('a mode name alone does not enable synthetic behavior', async () => {
    vi.stubEnv('VITE_PAWTEL_SHOWCASE', 'false');
    const api = await client();
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [] })),
    );
    await api.get('/listings');
    expect(fetch).toHaveBeenCalledOnce();
  });
});

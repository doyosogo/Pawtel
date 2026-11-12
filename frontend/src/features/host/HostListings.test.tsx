import { fireEvent, screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { HostGate } from './HostPage';
import { HostListingsPage } from './HostListingsPage';
import { ListingFormPage } from './ListingFormPage';
import { HostProfileForm } from './HostProfileForm';
import { ImageManager } from './ImageManager';
import { renderPage } from '../../test/render';
import { mockWorkflow } from '../../test/workflow';
import { json, listing, user } from '../../test/fixtures';
import type { HostListing } from './api';
const stay: HostListing = {
  ...listing,
  images: [],
  status: 'DRAFT',
  created_at: '',
  updated_at: '',
};
const image = {
  id: 'photo-one',
  url: 'https://res.cloudinary.com/demo/image/upload/one',
  alt_text: 'Garden',
  sort_order: 0,
};
afterEach(() => vi.unstubAllGlobals());
it('enables optional Host mode on the same account with bio only', async () => {
  let enabled = false;
  const fetcher = mockWorkflow((path, init) => {
    if (path.endsWith('/host/profile')) {
      if (init?.method === 'POST') {
        enabled = true;
        return json(
          { user_id: user.id, bio: 'Welcome', created_at: '', updated_at: '' },
          201,
        );
      }
      return enabled
        ? json({
            user_id: user.id,
            bio: 'Welcome',
            created_at: '',
            updated_at: '',
          })
        : json(
            {
              error: { code: 'host_profile_not_found', message: 'No profile' },
            },
            404,
          );
    }
  });
  renderPage(
    <Routes>
      <Route element={<HostGate />}>
        <Route path="*" element={<p>Host workspace ready</p>} />
      </Route>
    </Routes>,
  );
  fireEvent.change(await screen.findByLabelText('Host bio (optional)'), {
    target: { value: 'Welcome' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Become a Host' }));
  await screen.findByText('Host workspace ready');
  const call = fetcher.mock.calls.find(([, init]) => init?.method === 'POST')!;
  expect(JSON.parse(call[1].body)).toEqual({ bio: 'Welcome' });
});
it('updates the existing Host bio without submitting identity', async () => {
  const fetcher = mockWorkflow((path, init) =>
    path.endsWith('/host/profile') && init?.method === 'PATCH'
      ? json({ bio: 'Updated' })
      : undefined,
  );
  renderPage(<HostProfileForm bio="Original" />);
  fireEvent.change(screen.getByLabelText('Host bio (optional)'), {
    target: { value: 'Updated' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save bio' }));
  await screen.findByText('Host profile saved.');
  expect(
    JSON.parse(
      fetcher.mock.calls.find(([, init]) => init?.method === 'PATCH')![1].body,
    ),
  ).toEqual({ bio: 'Updated' });
});
it('renders Host collection and archived filtering', async () => {
  const fetcher = mockWorkflow((path) =>
    path.includes('/host/listings')
      ? json([
          { ...stay, status: path.includes('ARCHIVED') ? 'ARCHIVED' : 'DRAFT' },
        ])
      : undefined,
  );
  renderPage(<HostListingsPage />);
  await screen.findByRole('heading', { name: stay.title });
  expect(
    screen.getByRole('link', { name: 'Edit Listing & photos' }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Listing status'), {
    target: { value: 'ARCHIVED' },
  });
  await screen.findByText(/Archived Listings are read-only/);
  expect(
    fetcher.mock.calls.some(([path]) => path.includes('status=ARCHIVED')),
  ).toBe(true);
});
function fillNew() {
  fireEvent.change(screen.getByLabelText('Listing title'), {
    target: { value: 'Garden stay' },
  });
  fireEvent.change(screen.getByLabelText('Description'), {
    target: { value: 'A quiet fictional stay.' },
  });
  fireEvent.change(screen.getByLabelText('Suburb'), {
    target: { value: 'Norwood' },
  });
  fireEvent.change(screen.getByLabelText('Postcode'), {
    target: { value: '5067' },
  });
  fireEvent.change(screen.getByLabelText('Base nightly price (AUD)'), {
    target: { value: '55.29' },
  });
  fireEvent.change(
    screen.getByLabelText('Additional-pet nightly price (AUD)'),
    { target: { value: '20.01' } },
  );
  fireEvent.click(screen.getByLabelText('Dogs'));
}
it('creates a DRAFT with exact cents/species and no Host identity or lifecycle fields', async () => {
  const fetcher = mockWorkflow((path, init) =>
    path.endsWith('/host/listings') && init?.method === 'POST'
      ? json({ ...stay, id: 'created-id' }, 201)
      : undefined,
  );
  renderPage(<ListingFormPage create />, {
    path: '/host/listings/new',
    route: '/host/listings/new',
  });
  fillNew();
  fireEvent.click(screen.getByRole('button', { name: 'Create draft' }));
  await screen.findAllByText('/host/listings/created-id/edit');
  const body = JSON.parse(
    fetcher.mock.calls.find(([, init]) => init?.method === 'POST')![1].body,
  );
  expect(body).toEqual({
    title: 'Garden stay',
    description: 'A quiet fictional stay.',
    suburb: 'Norwood',
    state: 'SA',
    postcode: '5067',
    max_pet_capacity: 1,
    base_nightly_price_cents: 5529,
    additional_pet_price_cents: 2001,
    accepted_species: ['DOG'],
  });
});
it('rejects excessive decimals before sending a Listing', async () => {
  const fetcher = mockWorkflow();
  renderPage(<ListingFormPage create />);
  fillNew();
  fireEvent.change(screen.getByLabelText('Base nightly price (AUD)'), {
    target: { value: '55.001' },
  });
  fireEvent.submit(screen.getByLabelText('Listing title').closest('form')!);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'two decimal places',
  );
  expect(fetcher.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(
    false,
  );
});
it('edits using only changed fields and refreshes relevant collections', async () => {
  const fetcher = mockWorkflow((path, init) =>
    path.endsWith(`/host/listings/${listing.id}`)
      ? json(init?.method === 'PATCH' ? { ...stay, title: 'Updated' } : stay)
      : undefined,
  );
  const { client } = renderPage(<ListingFormPage />, {
    path: `/host/listings/${listing.id}/edit`,
    route: '/host/listings/:listingId/edit',
  });
  const invalidation = vi.spyOn(client, 'invalidateQueries');
  fireEvent.change(await screen.findByLabelText('Listing title'), {
    target: { value: 'Updated' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  await screen.findByText('Listing details saved.');
  expect(
    JSON.parse(
      fetcher.mock.calls.find(([, init]) => init?.method === 'PATCH')![1].body,
    ),
  ).toEqual({ title: 'Updated' });
  expect(invalidation).toHaveBeenCalledWith({ queryKey: ['listings'] });
});
it.each(['listing_not_ready', 'listing_capacity_reserved'])(
  'surfaces backend %s errors',
  async (code) => {
    mockWorkflow((path, init) =>
      path.endsWith(`/host/listings/${listing.id}`)
        ? init?.method === 'PATCH'
          ? json({ error: { code, message: 'Conflict' } }, 409)
          : json(stay)
        : undefined,
    );
    renderPage(<ListingFormPage />, {
      path: `/host/listings/${listing.id}/edit`,
      route: '/host/listings/:listingId/edit',
    });
    await screen.findByLabelText('Listing title');
    if (code === 'listing_not_ready')
      fireEvent.click(screen.getByRole('button', { name: 'Publish listing' }));
    else {
      fireEvent.change(screen.getByLabelText('Maximum pet capacity'), {
        target: { value: '1' },
      });
      fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    }
    expect(await screen.findByRole('alert')).toHaveTextContent(
      code === 'listing_not_ready'
        ? 'accepted species'
        : 'existing reservations',
    );
  },
);
it('archives only after confirmation using the archive endpoint', async () => {
  let archived = false;
  const fetcher = mockWorkflow((path, init) => {
    if (init?.method === 'DELETE') {
      archived = true;
      return new Response(null, { status: 204 });
    }
    if (path.includes('/host/listings')) return json(archived ? [] : [stay]);
  });
  renderPage(<HostListingsPage />);
  fireEvent.click(
    await screen.findByRole('button', { name: 'Archive listing' }),
  );
  expect(fetcher.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(
    false,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Confirm archive' }));
  await screen.findByText(/No Listings here yet/);
});
it('uploads binary photos with credentials/CSRF and no provider credentials', async () => {
  const fetcher = mockWorkflow((path, init) =>
    path.includes('/images?') && init?.method === 'POST'
      ? json(image, 201)
      : undefined,
  );
  renderPage(<ImageManager listing={stay} />);
  const file = new File(['synthetic content'], 'photo.png', {
    type: 'image/png',
  });
  fireEvent.change(screen.getByLabelText('Choose photo'), {
    target: { files: [file] },
  });
  fireEvent.change(screen.getByLabelText('Photo description (optional)'), {
    target: { value: 'Garden' },
  });
  fireEvent.submit(screen.getByLabelText('Choose photo').closest('form')!);
  await screen.findByText('Photos updated.');
  const call = fetcher.mock.calls.find(([path]) => path.includes('/images?'))!;
  expect(call[1]).toMatchObject({
    credentials: 'include',
    body: file,
    headers: {
      'Content-Type': 'image/png',
      'X-CSRF-Token': 'nonce',
      'X-PAWTEL-Request': '1',
    },
  });
});
it.each([
  ['image/svg+xml', 1],
  ['image/png', 5 * 1024 * 1024 + 1],
])('rejects invalid upload %s/%s before sending', async (type, size) => {
  const fetcher = mockWorkflow();
  renderPage(<ImageManager listing={stay} />);
  const file = new File(['x'], 'bad', { type });
  Object.defineProperty(file, 'size', { value: size });
  fireEvent.change(screen.getByLabelText('Choose photo'), {
    target: { files: [file] },
  });
  fireEvent.submit(screen.getByLabelText('Choose photo').closest('form')!);
  await screen.findByRole('alert');
  expect(fetcher.mock.calls.some(([path]) => path.includes('/images?'))).toBe(
    false,
  );
});
it('reorders with accessible controls and removes images with cleanup feedback', async () => {
  const second = { ...image, id: 'two', sort_order: 1 };
  const fetcher = mockWorkflow((path) =>
    path.endsWith('/images/order')
      ? json([second, image])
      : path.endsWith('/images/photo-one')
        ? json({ cleanup_pending: true })
        : undefined,
  );
  renderPage(<ImageManager listing={{ ...stay, images: [image, second] }} />);
  fireEvent.click(screen.getByRole('button', { name: 'Move photo 2 earlier' }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([path]) => path.endsWith('/images/order')),
    ).toBe(true),
  );
  await screen.findByText('Photos updated.');
  expect(
    JSON.parse(
      fetcher.mock.calls.find(([path]) => path.endsWith('/images/order'))![1]
        .body,
    ),
  ).toEqual({ image_ids: ['two', 'photo-one'] });
  fireEvent.click(screen.getByRole('button', { name: 'Remove photo 1' }));
  await screen.findByText(/Storage cleanup is pending/);
});
it.each(['DRAFT', 'PUBLISHED'] as const)(
  'changes lifecycle explicitly from %s and refreshes the collection',
  async (initial) => {
    let status: HostListing['status'] = initial;
    const fetcher = mockWorkflow((path, init) => {
      if (init?.method === 'PATCH') {
        status = JSON.parse(init.body as string).status;
        return json({ ...stay, status });
      }
      if (path.includes('/host/listings')) return json([{ ...stay, status }]);
    });
    renderPage(<HostListingsPage />);
    fireEvent.click(
      await screen.findByRole('button', {
        name: initial === 'DRAFT' ? 'Publish listing' : 'Move to draft',
      }),
    );
    await screen.findByRole('button', {
      name: initial === 'DRAFT' ? 'Move to draft' : 'Publish listing',
    });
    expect(
      JSON.parse(
        fetcher.mock.calls.find(([, init]) => init?.method === 'PATCH')![1]
          .body,
      ),
    ).toEqual({ status: initial === 'DRAFT' ? 'PUBLISHED' : 'DRAFT' });
  },
);
it('previews the selected photo and revokes the temporary URL on unmount', () => {
  const revoke = vi.fn();
  vi.stubGlobal(
    'URL',
    class extends URL {
      static createObjectURL = vi.fn(() => 'blob:synthetic-photo');
      static revokeObjectURL = revoke;
    },
  );
  mockWorkflow();
  const { unmount } = renderPage(<ImageManager listing={stay} />);
  fireEvent.change(screen.getByLabelText('Choose photo'), {
    target: {
      files: [new File(['synthetic'], 'photo.png', { type: 'image/png' })],
    },
  });
  expect(screen.getByAltText('Selected photo preview')).toHaveAttribute(
    'src',
    'blob:synthetic-photo',
  );
  unmount();
  expect(revoke).toHaveBeenCalledWith('blob:synthetic-photo');
});

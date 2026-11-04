import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PetsPage } from './PetsPage';
import { renderPage } from '../../test/render';
import { dog, cat, mockWorkflow } from '../../test/workflow';
import { json } from '../../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
it('renders active pets and refetches archived filtering', async () => {
  const fetcher = mockWorkflow((path) =>
    path.includes('include_archived=true')
      ? json([dog, { ...cat, is_active: false }])
      : undefined,
  );
  renderPage(<PetsPage />);
  expect(
    await screen.findByRole('heading', { name: 'Milo' }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText('Show archived pets'));
  expect(await screen.findByText('Archived')).toBeInTheDocument();
  expect(
    fetcher.mock.calls.some(([path]) => path.includes('include_archived=true')),
  ).toBe(true);
  expect(
    screen.queryByRole('button', { name: 'Edit Luna' }),
  ).not.toBeInTheDocument();
});
it('creates with editable fields only and refreshes the collection', async () => {
  let saved = false;
  const fetcher = mockWorkflow((path, init) => {
    if (path.endsWith('/pets') && init?.method === 'POST') {
      saved = true;
      return json({ ...dog, name: 'Poppy' }, 201);
    }
    if (path.includes('/pets?'))
      return json(saved ? [{ ...dog, name: 'Poppy' }] : []);
  });
  const { client } = renderPage(<PetsPage />);
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  fireEvent.click(screen.getByRole('button', { name: 'Add a pet' }));
  fireEvent.change(screen.getByLabelText('Pet name'), {
    target: { value: ' Poppy ' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save pet' }));
  expect(
    await screen.findByRole('heading', { name: 'Poppy' }),
  ).toBeInTheDocument();
  const call = fetcher.mock.calls.find(
    ([path, init]) => path.endsWith('/pets') && init?.method === 'POST',
  )!;
  expect(JSON.parse(call[1].body)).toEqual({
    name: 'Poppy',
    species: 'DOG',
    breed: null,
    date_of_birth: null,
  });
  expect(call[1].credentials).toBe('include');
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['pets'] });
});
it('validates blank names and future birth dates without sending owner identity', async () => {
  const fetcher = mockWorkflow();
  renderPage(<PetsPage />);
  fireEvent.click(screen.getByRole('button', { name: 'Add a pet' }));
  fireEvent.change(screen.getByLabelText('Pet name'), {
    target: { value: '   ' },
  });
  fireEvent.submit(screen.getByLabelText('Pet name').closest('form')!);
  expect(await screen.findByRole('alert')).toHaveTextContent('Enter a name');
  fireEvent.change(screen.getByLabelText('Pet name'), {
    target: { value: 'Milo' },
  });
  fireEvent.change(screen.getByLabelText('Date of birth (optional)'), {
    target: { value: '2999-01-01' },
  });
  fireEvent.submit(screen.getByLabelText('Pet name').closest('form')!);
  expect(fetcher.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(
    false,
  );
});
it('shows backend validation errors and allows editing', async () => {
  const fetcher = mockWorkflow((_path, init) =>
    init?.method === 'PATCH'
      ? json(
          {
            error: {
              code: 'validation_error',
              message: 'Invalid request data.',
            },
          },
          422,
        )
      : undefined,
  );
  renderPage(<PetsPage />);
  fireEvent.click(await screen.findByRole('button', { name: 'Edit Milo' }));
  fireEvent.change(screen.getByLabelText('Breed (optional)'), {
    target: { value: 'Terrier' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save pet' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'check your details',
  );
  const call = fetcher.mock.calls.find(([, init]) => init?.method === 'PATCH')!;
  expect(JSON.parse(call[1].body)).toEqual({
    name: 'Milo',
    species: 'DOG',
    breed: 'Terrier',
    date_of_birth: null,
  });
});
it('requires inline archive confirmation and preserves history', async () => {
  let archived = false;
  const fetcher = mockWorkflow((path, init) => {
    if (init?.method === 'DELETE') {
      archived = true;
      return new Response(null, { status: 204 });
    }
    if (path.includes('/pets?')) return json(archived ? [cat] : [dog, cat]);
  });
  renderPage(<PetsPage />);
  fireEvent.click(await screen.findByRole('button', { name: 'Archive Milo' }));
  expect(fetcher.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(
    false,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Keep pet' }));
  fireEvent.click(screen.getByRole('button', { name: 'Archive Milo' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm archive' }));
  await waitFor(() =>
    expect(
      screen.queryByRole('button', { name: 'Archive Milo' }),
    ).not.toBeInTheDocument(),
  );
  expect(screen.getByText(/Pet archived/)).toHaveTextContent(
    'history is preserved',
  );
  const call = fetcher.mock.calls.find(
    ([, init]) => init?.method === 'DELETE',
  )!;
  expect(call[0]).toBe('/api/v1/pets/dog-id');
  expect(JSON.parse(call[1].body)).toEqual({});
});
it('saves edits and refetches the current pet list', async () => {
  let name = 'Milo';
  mockWorkflow((path, init) => {
    if (init?.method === 'PATCH') {
      name = JSON.parse(init.body as string).name;
      return json({ ...dog, name });
    }
    if (path.includes('/pets?')) return json([{ ...dog, name }]);
  });
  renderPage(<PetsPage />);
  fireEvent.click(await screen.findByRole('button', { name: 'Edit Milo' }));
  fireEvent.change(screen.getByLabelText('Pet name'), {
    target: { value: 'Milo Junior' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save pet' }));
  expect(
    await screen.findByRole('heading', { name: 'Milo Junior' }),
  ).toBeInTheDocument();
  expect(screen.queryByLabelText('Pet name')).not.toBeInTheDocument();
});

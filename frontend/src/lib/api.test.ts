import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, get, write } from './api';
import { anonymous, json } from '../test/fixtures';
afterEach(() => vi.unstubAllGlobals());
describe('cookie API boundary', () => {
  it('includes credentials on reads', async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ ok: true }));
    vi.stubGlobal('fetch', fetcher);
    await get('/auth/me');
    expect(fetcher).toHaveBeenCalledWith(
      '/api/v1/auth/me',
      expect.objectContaining({ credentials: 'include' }),
    );
  });
  it('gets current CSRF and sends required write headers', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ csrf_token: 'nonce' }))
      .mockResolvedValueOnce(json({ id: 'pet' }));
    vi.stubGlobal('fetch', fetcher);
    await write('/pets', { name: 'Milo' });
    expect(fetcher.mock.calls[1]).toEqual([
      '/api/v1/pets',
      expect.objectContaining({
        credentials: 'include',
        method: 'POST',
        body: '{"name":"Milo"}',
        headers: {
          'Content-Type': 'application/json',
          'X-PAWTEL-Request': '1',
          'X-CSRF-Token': 'nonce',
        },
      }),
    ]);
  });
  it('permits anonymous login without bypassing private writes', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(anonymous())
      .mockResolvedValueOnce(json({ id: 'user' }));
    vi.stubGlobal('fetch', fetcher);
    await write('/auth/login', {
      email: 'a@example.test',
      password: 'transient',
    });
    expect(fetcher.mock.calls[1][1].headers).not.toHaveProperty('X-CSRF-Token');
    fetcher.mockReset().mockResolvedValue(anonymous());
    await expect(write('/pets', {})).rejects.toMatchObject({ status: 401 });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('supports 204 logout without parsing JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(json({ csrf_token: 'nonce' }))
        .mockResolvedValueOnce(new Response(null, { status: 204 })),
    );
    await expect(write('/auth/logout')).resolves.toBeUndefined();
  });
  it('preserves machine error codes without leaking response payloads', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json(
          {
            error: {
              code: 'invalid_credentials',
              message: 'Email or password is incorrect.',
            },
          },
          401,
        ),
      ),
    );
    await expect(get('/auth/me')).rejects.toMatchObject({
      code: 'invalid_credentials',
      status: 401,
    });
  });
  it('reports network errors and keeps abort semantics', async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError('failed'));
    vi.stubGlobal('fetch', fetcher);
    await expect(get('/listings')).rejects.toBeInstanceOf(ApiError);
    fetcher.mockRejectedValue(new DOMException('cancelled', 'AbortError'));
    await expect(get('/listings')).rejects.toHaveProperty('name', 'AbortError');
  });
});

it('keeps a safe backend request reference on errors for support', async () => {
  const reference = 'ebcc924a-46a2-47d0-8e13-a9d732f0d515';
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'internal_error' } }), {
        status: 500,
        headers: { 'X-Request-ID': reference },
      }),
    ),
  );
  await expect(get('/anything')).rejects.toMatchObject({
    requestId: reference,
  });
});

it('ignores untrusted request reference text', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response('{}', {
        status: 500,
        headers: { 'X-Request-ID': 'unsafe-reference' },
      }),
    ),
  );
  await expect(get('/anything')).rejects.toMatchObject({
    requestId: undefined,
  });
});

it('resolves one same-origin API base and rejects absolute endpoint paths', async () => {
  const { apiPath } = await import('./api');
  expect(apiPath('/auth/me')).toBe('/api/v1/auth/me');
  expect(() => apiPath('https://other.example.com')).toThrow();
  expect(() => apiPath('//other.example.com')).toThrow();
});

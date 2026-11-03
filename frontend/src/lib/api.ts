export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function send<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...init,
      credentials: 'include',
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError')
      throw error;
    throw new ApiError(
      0,
      'network_error',
      'We couldn’t reach PAWTEL. Please try again.',
    );
  }
  if (response.status === 204) return undefined as T;
  let data;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(
      response.status,
      'invalid_response',
      'Something went wrong. Please try again.',
    );
  }
  if (!response.ok) {
    throw new ApiError(
      response.status,
      data?.error?.code ?? 'request_failed',
      data?.error?.message ?? 'Your request could not be completed.',
    );
  }
  return data as T;
}

export function get<T>(path: string, signal?: AbortSignal) {
  return send<T>(path, { signal });
}

export async function write<T>(
  path: string,
  body: unknown = {},
  method = 'POST',
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-PAWTEL-Request': '1',
  };
  try {
    const csrf = await get<{ csrf_token: string }>('/auth/csrf');
    headers['X-CSRF-Token'] = csrf.csrf_token;
  } catch (error) {
    const anonymousAllowed = [
      '/auth/login',
      '/auth/register',
      '/auth/logout',
    ].includes(path);
    if (!(
      anonymousAllowed &&
      error instanceof ApiError &&
      error.status === 401
    ))
      throw error;
  }
  // CSRF is a per-request nonce, never an authentication/session credential.
  return send<T>(path, { method, headers, body: JSON.stringify(body) });
}

export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError))
    return 'Something went wrong. Please try again.';
  const messages: Record<string, string> = {
    invalid_credentials:
      'That email and password don’t match. Please try again.',
    email_already_registered:
      'An account with that email already exists. Try signing in.',
    registration_unavailable:
      'We couldn’t create an account with those details. If you already have an account, try logging in.',
    email_exists: 'An account with that email already exists. Try signing in.',
    account_inactive: 'Your account is inactive. You can sign out below.',
    email_not_verified:
      'Please verify your email before using hosting or booking tools.',
    validation_error: 'Please check your details and try again.',
    csrf_failed: 'Your session changed. Please try again.',
    authentication_required: 'Please sign in to continue.',
  };
  return (
    messages[error.code] ??
    (error.status >= 500
      ? 'PAWTEL is taking a moment. Please try again shortly.'
      : error.message)
  );
}

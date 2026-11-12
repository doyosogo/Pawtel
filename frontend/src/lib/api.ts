export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
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
  const suppliedId = response.headers.get('X-Request-ID');
  const requestId =
    suppliedId &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      suppliedId,
    )
      ? suppliedId
      : undefined;
  if (response.status === 204) return undefined as T;
  let data;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(
      response.status,
      'invalid_response',
      'Something went wrong. Please try again.',
      requestId,
    );
  }
  if (!response.ok) {
    throw new ApiError(
      response.status,
      data?.error?.code ?? 'request_failed',
      data?.error?.message ?? 'Your request could not be completed.',
      requestId,
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
    payments_not_configured:
      'Sandbox payments are not configured. Return to your Booking and try later.',
    booking_not_payable:
      'This Booking is no longer awaiting payment. Refresh its status.',
    payment_window_closed:
      'The payment window has closed or has too little time remaining. Check your Booking status.',
    payment_reconciliation_required:
      'Your payment is being checked. Do not submit another payment; refresh your Booking status later.',
    checkout_not_open:
      'This checkout is no longer open. Check your Booking status before trying again.',
    checkout_rejected:
      'The secure checkout could not be opened. Check your Booking before trying again.',
    checkout_temporarily_unavailable:
      'Checkout is temporarily unavailable. Check your Booking status; you can retry opening checkout for this Booking.',
    host_profile_exists:
      'Host mode is already enabled. Refresh your workspace.',
    host_profile_required: 'Become a Host before managing Listings.',
    listing_not_found:
      'This Listing is unavailable or does not belong to your account.',
    listing_archived: 'Archived Listings are read-only and cannot be restored.',
    listing_not_ready:
      'Choose at least one accepted species before publishing.',
    listing_capacity_reserved:
      'Capacity cannot be reduced below existing reservations. Keep enough space for accepted stays.',
    media_not_configured:
      'Photo storage is not configured yet. Your Listing details are saved separately; try uploading after storage setup.',
    media_provider_failed:
      'The photo upload could not be confirmed. Refresh your Listing before retrying. Any incomplete upload is tracked for cleanup.',
    media_association_failed:
      'The photo could not be linked to your Listing. Refresh before retrying; storage cleanup is tracked.',
    image_limit:
      'A Listing supports six images, including pending cleanup. Remove a photo or try after cleanup.',
    image_changed:
      'Photos have changed. Refresh your Listing before trying again.',
    booking_capacity_unavailable:
      'Those dates are no longer available for this request. Try different dates or fewer pets.',
    booking_busy:
      'This booking is being updated. Refresh it before trying again.',
    booking_invalid_state:
      'This booking has changed. Refresh to see its current status.',
    listing_unavailable:
      'This Listing is no longer available for a request or acceptance.',
    pet_not_available:
      'One or more pets are no longer eligible. Refresh your pets and choose active pets you own.',
    pet_not_accepted:
      'This Listing does not accept the species of one or more selected pets.',
    invalid_booking_dates:
      'Choose current or future stay dates, with checkout after check-in.',
    booking_owner_unavailable:
      'The Owner is no longer eligible for this booking.',
    self_booking_not_allowed:
      'You cannot request a booking at your own Listing.',
    booking_not_found:
      'This booking is unavailable or does not belong to your account.',
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

// Only this ownership-protected endpoint accepts binary images; JSON writes keep their contract.
export async function uploadImage(listingId: string, file: File, alt: string) {
  const csrf = await get<{ csrf_token: string }>('/auth/csrf');
  return send(
    `/host/listings/${encodeURIComponent(listingId)}/images?${new URLSearchParams({ alt_text: alt })}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': file.type,
        'X-PAWTEL-Request': '1',
        'X-CSRF-Token': csrf.csrf_token,
      },
      body: file,
    },
  );
}

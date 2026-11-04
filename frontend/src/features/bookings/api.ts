import { useQuery, useQueryClient } from '@tanstack/react-query';
import { get, write } from '../../lib/api';
import { useSession } from '../auth/session';
import type { Pet } from '../pets/api';
export type BookingStatus =
  | 'REQUESTED'
  | 'DECLINED'
  | 'AWAITING_PAYMENT'
  | 'CONFIRMED'
  | 'PAYMENT_FAILED'
  | 'CANCELLED'
  | 'COMPLETED'
  | 'EXPIRED';
export interface Booking {
  id: string;
  listing: { id: string; title: string; suburb: string; state: string };
  pets: Omit<Pet, 'created_at' | 'updated_at'>[];
  owner_display_name: string;
  check_in: string;
  check_out: string;
  status: BookingStatus;
  nightly_base_price_cents: number;
  additional_pet_price_cents: number;
  subtotal_cents: number;
  service_fee_cents: number;
  total_cents: number;
  payment_expires_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface BookingInput {
  listing_id: string;
  pet_ids: string[];
  check_in: string;
  check_out: string;
}
export const bookingPath = (host: boolean) =>
  host ? '/host/bookings' : '/bookings';
export const bookingUrl = (host: boolean) =>
  host ? '/host/bookings' : '/account/bookings';
export function useBookings(
  host: boolean,
  id?: string,
  status = '',
  offset = 0,
) {
  const session = useSession();
  const user =
    session.data?.state === 'authenticated' ? session.data.user : null;
  const params = new URLSearchParams({ limit: '20', offset: String(offset) });
  if (status) params.set('status', status);
  return useQuery({
    queryKey: [
      'bookings',
      user?.id,
      host ? 'host' : 'owner',
      id ?? 'collection',
      status,
      offset,
    ],
    queryFn: ({ signal }) =>
      get<Booking | Booking[]>(
        `${bookingPath(host)}${id ? `/${encodeURIComponent(id)}` : `?${params}`}`,
        signal,
      ),
    enabled: !!user?.email_verified_at,
    retry: false,
    meta: { private: true },
  });
}
export const requestBooking = (input: BookingInput) =>
  write<Booking>('/bookings', input);
export const actOnBooking = (
  host: boolean,
  id: string,
  action: 'accept' | 'decline' | 'cancel',
) => write<Booking>(`${bookingPath(host)}/${encodeURIComponent(id)}/${action}`);
export function useRefreshBookings() {
  const client = useQueryClient();
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['bookings'] }),
      client.invalidateQueries({ queryKey: ['availability'] }),
      client.invalidateQueries({ queryKey: ['listings'] }),
    ]);
  };
}

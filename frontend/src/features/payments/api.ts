import { write } from '../../lib/api';
export interface CheckoutSession {
  payment_attempt_id: string;
  client_secret: string;
  expires_at: string;
}
// Call from local component state only: never a Query/Mutation cache or storage.
export const startCheckout = (bookingId: string) =>
  write<CheckoutSession>(
    `/bookings/${encodeURIComponent(bookingId)}/checkout-session`,
  );
export const paymentReturnPath = (bookingId: string) =>
  `/account/bookings/${encodeURIComponent(bookingId)}/payment-return`;

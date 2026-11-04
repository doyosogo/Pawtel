import type { BookingStatus as Status } from './api';
export const statusLabels: Record<Status, string> = {
  REQUESTED: 'Waiting for host',
  DECLINED: 'Declined by host',
  AWAITING_PAYMENT: 'Payment required',
  CONFIRMED: 'Confirmed',
  PAYMENT_FAILED: 'Payment failed',
  CANCELLED: 'Cancelled',
  COMPLETED: 'Completed',
  EXPIRED: 'Payment window expired',
};

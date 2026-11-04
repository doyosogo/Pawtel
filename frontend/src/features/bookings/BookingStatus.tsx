import type { BookingStatus as Status } from './api';
import { statusLabels } from './status';
export function BookingStatus({ status }: { status: Status }) {
  return (
    <span className={`booking-status status-${status.toLowerCase()}`}>
      {statusLabels[status]}
    </span>
  );
}

import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { get } from '../../lib/api';
import { useSession } from '../auth/session';
import { RequestError } from '../account/RequestError';
import { BookingStatus } from '../bookings/BookingStatus';
import type { Booking } from '../bookings/api';
import { PaymentSummary } from './PaymentSummary';

function BookingPaymentStatus({
  bookingId,
  userId,
}: {
  bookingId: string;
  userId: string;
}) {
  const [started] = useState(Date.now);
  const query = useQuery({
    queryKey: ['bookings', userId, 'owner', bookingId, 'payment-return'],
    queryFn: ({ signal }) =>
      get<Booking>(`/bookings/${encodeURIComponent(bookingId)}`, signal),
    staleTime: 0,
    retry: false,
    meta: { private: true },
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchInterval: (state) =>
      !state.state.error &&
      state.state.data?.status === 'AWAITING_PAYMENT' &&
      state.state.dataUpdateCount < 10 &&
      Date.now() - started < 30_000
        ? 3000
        : false,
  });
  if (query.isPending || (!query.isError && !query.isFetchedAfterMount))
    return <p role="status">Checking payment status…</p>;
  if (query.isError)
    return (
      <RequestError error={query.error} retry={() => void query.refetch()} />
    );
  const booking = query.data;
  return (
    <>
      <h1>
        {booking.status === 'CONFIRMED'
          ? 'Your stay is confirmed'
          : booking.status === 'AWAITING_PAYMENT'
            ? 'Waiting for payment confirmation'
            : 'Booking status'}
      </h1>
      <BookingStatus status={booking.status} />
      <p role="status">
        {booking.status === 'CONFIRMED'
          ? 'PAWTEL has received payment confirmation. Your Booking is confirmed.'
          : booking.status === 'AWAITING_PAYMENT'
            ? 'PAWTEL is still waiting for payment confirmation. This page checks briefly, then stops automatically. A browser return does not confirm payment.'
            : 'This is the latest Booking state returned by PAWTEL.'}
      </p>
      {booking.status === 'CANCELLED' && (
        <p>
          If a payment completed around cancellation, PAWTEL retains the
          cancellation and flags the payment for reconciliation. This page
          cannot issue a refund.
        </p>
      )}
      <div className="action-row">
        <button
          className="button secondary"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          Refresh payment status
        </button>
        <Link
          className="button secondary"
          to={`/account/bookings/${booking.id}`}
        >
          View Booking
        </Link>
        {booking.status === 'AWAITING_PAYMENT' && (
          <Link to={`/account/bookings/${booking.id}/pay`}>
            Review payment / retry
          </Link>
        )}
      </div>
      <PaymentSummary booking={booking} />
    </>
  );
}
export function PaymentReturnPage() {
  const { bookingId } = useParams();
  const session = useSession();
  // Return query strings (including success/session IDs) are never authority or
  // propagated to login links. Remove unsolicited provider parameters on arrival.
  useEffect(() => {
    if (window.location.search || window.location.hash)
      window.history.replaceState(
        window.history.state,
        '',
        window.location.pathname,
      );
  }, []);
  const user =
    session.data?.state === 'authenticated' ? session.data.user : null;
  if (!bookingId)
    return (
      <>
        <h1>Checking payment status</h1>
        <p>Open your Booking to check its latest payment status.</p>
        <Link to="/account/bookings">My Bookings</Link>
      </>
    );
  if (!user) return <p role="status">Checking your session…</p>;
  return (
    <BookingPaymentStatus
      key={`${user.id}:${bookingId}`}
      bookingId={bookingId}
      userId={user.id}
    />
  );
}

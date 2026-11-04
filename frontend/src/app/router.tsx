import { createBrowserRouter } from 'react-router';
import { Layout } from './Layout';
import { HomePage } from '../pages/HomePage';
import { StaysPage } from '../pages/StaysPage';
import { AuthPage } from '../features/auth/AuthPage';
import { ListingDetailPage } from '../features/listings/ListingPage';
import { AccountPage, HostingPage } from '../pages/AccountPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { AccountGate } from '../features/account/AccountGate';
import { PetsPage } from '../features/pets/PetsPage';
import { BookingsPage } from '../features/bookings/BookingsPage';
import { BookingDetailPage } from '../features/bookings/BookingDetailPage';
import { HostGate, HostPage } from '../features/host/HostPage';
import { CheckoutPage } from '../features/payments/CheckoutPage';
import { PaymentReturnPage } from '../features/payments/PaymentReturnPage';
export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/stays', element: <StaysPage /> },
      { path: '/stays/:listingId', element: <ListingDetailPage /> },
      { path: '/login', element: <AuthPage key="login" /> },
      { path: '/register', element: <AuthPage key="register" register /> },
      { path: '/account', element: <AccountPage /> },
      { path: '/hosting', element: <HostingPage /> },
      {
        element: <AccountGate />,
        children: [{ path: '/account/pets', element: <PetsPage /> }],
      },
      {
        element: <AccountGate verified />,
        children: [
          { path: '/account/bookings', element: <BookingsPage /> },
          {
            path: '/account/bookings/:bookingId/pay',
            element: <CheckoutPage />,
          },
          {
            path: '/account/bookings/:bookingId/payment-return',
            element: <PaymentReturnPage />,
          },
          { path: '/checkout/return', element: <PaymentReturnPage /> },
          {
            path: '/account/bookings/:bookingId',
            element: <BookingDetailPage />,
          },
          {
            element: <HostGate />,
            children: [
              { path: '/host', element: <HostPage /> },
              { path: '/host/bookings', element: <BookingsPage host /> },
              {
                path: '/host/bookings/:bookingId',
                element: <BookingDetailPage host />,
              },
            ],
          },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);

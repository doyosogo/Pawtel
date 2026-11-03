import { createBrowserRouter } from 'react-router';
import { Layout } from './Layout';
import { HomePage } from '../pages/HomePage';
import { StaysPage } from '../pages/StaysPage';
import { AuthPage } from '../features/auth/AuthPage';
import { ListingDetailPage } from '../features/listings/ListingPage';
import { AccountPage, HostingPage } from '../pages/AccountPage';
import { NotFoundPage } from '../pages/NotFoundPage';
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
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);

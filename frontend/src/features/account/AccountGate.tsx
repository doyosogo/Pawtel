import { Link, Navigate, Outlet, useLocation } from 'react-router';
import { useSession } from '../auth/session';
import { RequestError } from './RequestError';

import { VerificationNotice } from './VerificationNotice';
export function AccountGate({ verified = false }: { verified?: boolean }) {
  const session = useSession();
  const location = useLocation();
  if (session.isPending)
    return (
      <p className="container simple-page" role="status">
        Checking your session…
      </p>
    );
  if (session.isError)
    return (
      <div className="container simple-page">
        <RequestError
          error={session.error}
          retry={() => void session.refetch()}
        />
      </div>
    );
  if (session.data.state === 'anonymous')
    return (
      <Navigate
        to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
        replace
      />
    );
  if (session.data.state === 'inactive')
    return (
      <div className="container simple-page">
        <h1>Account inactive</h1>
        <p>Please log out using the account menu.</p>
      </div>
    );
  return (
    <div className="container workspace">
      <nav className="workspace-nav" aria-label="Your PAWTEL">
        <Link to="/account">Account</Link>
        <Link to="/account/pets">My Pets</Link>
        <Link to="/account/bookings">My Bookings</Link>
        <Link to="/host">Host workspace</Link>
      </nav>
      {verified && !session.data.user.email_verified_at ? (
        <VerificationNotice />
      ) : (
        <Outlet />
      )}
    </div>
  );
}

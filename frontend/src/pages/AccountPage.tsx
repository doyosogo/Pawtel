import { Link, Navigate } from 'react-router';
import { useHostProfile, useSession } from '../features/auth/session';
import { errorMessage } from '../lib/api';

export function AccountPage() {
  const session = useSession();
  if (session.isPending)
    return (
      <div className="container simple-page" role="status">
        Checking your session…
      </div>
    );
  if (session.isError)
    return (
      <div className="container feedback" role="alert">
        <h1>We couldn’t load your account</h1>
        <p>{errorMessage(session.error)}</p>
        <button className="button" onClick={() => void session.refetch()}>
          Try again
        </button>
      </div>
    );
  if (session.data.state === 'anonymous')
    return <Navigate to="/login?next=%2Faccount" replace />;
  if (session.data.state === 'inactive')
    return (
      <div className="container simple-page">
        <h1>Account inactive</h1>
        <p>You can log out from the account menu.</p>
      </div>
    );
  const user = session.data.user;
  return (
    <div className="container simple-page">
      <p className="eyebrow">YOUR PAWTEL</p>
      <h1>Hello, {user.display_name}.</h1>
      <p className="lead">A little space for you and your companions.</p>
      <div className="account-card">
        <h2>Account details</h2>
        <dl>
          <dt>Name</dt>
          <dd>{user.display_name}</dd>
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>Email status</dt>
          <dd>{user.email_verified_at ? 'Verified' : 'Not verified yet'}</dd>
        </dl>
        {!user.email_verified_at && (
          <p className="notice">
            Email delivery isn’t configured in this demo. No verification email
            has been sent. Verified email is needed for hosting and bookings.
          </p>
        )}
      </div>
      <nav className="action-row" aria-label="Account tools">
        <Link className="button secondary" to="/account/pets">
          My Pets
        </Link>
        <Link className="button secondary" to="/account/bookings">
          My Bookings
        </Link>
        <Link className="button secondary" to="/host">
          Host workspace
        </Link>
      </nav>
      <Link className="button secondary" to="/stays">
        Explore stays
      </Link>
    </div>
  );
}
export function HostingPage() {
  const session = useSession();
  const profile = useHostProfile(session.data);
  const user =
    session.data?.state === 'authenticated' ? session.data.user : null;
  return (
    <div className="container hosting-page">
      <div className="hosting-copy">
        <p className="eyebrow">A LITTLE SPACE. A LOT OF LOVE.</p>
        <h1>
          {profile.data
            ? 'Welcome to your host space.'
            : 'Their happy place could be your home.'}
        </h1>
        <p className="lead">One PAWTEL account, for all the ways you care.</p>
        {session.isPending ? (
          <p role="status">Checking your account…</p>
        ) : session.isError ? (
          <p role="alert">{errorMessage(session.error)}</p>
        ) : profile.isError ? (
          <p role="alert">{errorMessage(profile.error)}</p>
        ) : profile.isFetching ? (
          <p role="status">Checking your Host profile…</p>
        ) : profile.data ? (
          <div className="notice">
            <strong>Your Host profile is enabled.</strong>
            <p>{profile.data.bio ?? 'You haven’t added a bio yet.'}</p>
            <p>
              <Link to="/host">Open your Host workspace</Link>. Listing editors
              are coming later.
            </p>
          </div>
        ) : (
          <>
            <p>
              Hosting on PAWTEL means welcoming dogs or cats for boarding stays.
              You can be a host and a pet owner with the same account.
            </p>
            <p>
              Host setup tools are coming to this website next. Hosting requires
              an active account with a verified email.
            </p>
            {!user && session.data?.state !== 'inactive' && (
              <Link className="button" to="/register?next=%2Fhosting">
                Create an account
              </Link>
            )}
            {user && !user.email_verified_at && (
              <p className="notice">
                Your email is not verified. Email delivery is not configured in
                this demo yet.
              </p>
            )}
          </>
        )}
        <Link className="text-link" to="/stays">
          Explore the marketplace →
        </Link>
      </div>
      <img src="/media/cottage.svg" alt="" />
    </div>
  );
}

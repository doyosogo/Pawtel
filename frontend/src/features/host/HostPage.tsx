import { useBookings, type Booking } from '../bookings/api';
import { Link, Outlet } from 'react-router';
import { useHostProfile, useSession } from '../auth/session';
import { RequestError } from '../account/RequestError';
import { HostProfileForm } from './HostProfileForm';
import { useHostListings, type HostListing } from './api';
export function HostGate() {
  const session = useSession();
  const profile = useHostProfile(session.data);
  if (profile.isPending) return <p role="status">Checking Host profile…</p>;
  if (profile.isError)
    return (
      <RequestError
        error={profile.error}
        retry={() => void profile.refetch()}
      />
    );
  if (!profile.data)
    return (
      <>
        <h1>Your Host workspace</h1>
        <HostProfileForm onboard />
      </>
    );
  return (
    <>
      <nav className="workspace-nav" aria-label="Host tools">
        <Link to="/host">Overview</Link>
        <Link to="/host/listings">My Listings</Link>
        <Link to="/host/bookings">Booking inbox</Link>
      </nav>
      <Outlet />
    </>
  );
}
export function HostPage() {
  const session = useSession();
  const profile = useHostProfile(session.data);
  const listings = useHostListings();
  const inbox = useBookings(true, undefined, 'REQUESTED');
  const pending = inbox.data as Booking[] | undefined;
  const items = listings.data as HostListing[] | undefined;
  return (
    <>
      <p className="eyebrow">WELCOME HOME, HOST</p>
      <h1>Your Host workspace</h1>
      <p>Welcome pets, prepare your Listings and review incoming requests.</p>
      <div className="action-row">
        <Link className="button" to="/host/listings/new">
          Create Listing
        </Link>
        <Link className="button secondary" to="/host/listings">
          My Listings
        </Link>
        <Link className="button secondary" to="/host/bookings">
          Open booking inbox
        </Link>
      </div>
      {listings.isPending ? (
        <p role="status">Loading Listings…</p>
      ) : listings.isError ? (
        <RequestError error={listings.error} />
      ) : (
        <p>
          {items?.filter((l) => l.status === 'PUBLISHED').length ?? 0} published
          · {items?.filter((l) => l.status === 'DRAFT').length ?? 0} drafts.{' '}
          <Link to="/host/listings?status=ARCHIVED">View archived</Link>
        </p>
      )}
      <section className="workspace-panel">
        <h2>Booking requests</h2>
        {inbox.isPending ? (
          <p role="status">Checking requests…</p>
        ) : inbox.isError ? (
          <RequestError error={inbox.error} />
        ) : (
          <p>
            {pending?.length === 20 ? '20+' : (pending?.length ?? 0)} requests
            waiting for review.{' '}
            <Link to="/host/bookings?status=REQUESTED">Review requests</Link>
          </p>
        )}
      </section>
      <HostProfileForm bio={profile.data?.bio} />
    </>
  );
}

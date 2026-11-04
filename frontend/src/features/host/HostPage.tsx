import { Link, Outlet } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useHostProfile, useSession } from '../auth/session';
import { get } from '../../lib/api';
import { aud } from '../listings/api';
import { RequestError } from '../account/RequestError';
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
      <section className="workspace-panel">
        <h1>Your Host workspace</h1>
        <p>
          You do not have a Host profile yet. Host setup and Listing editors are
          coming in a later step.
        </p>
        <p>For local testing, use the synthetic demo Host from the README.</p>
        <Link to="/stays">Explore stays</Link>
      </section>
    );
  return <Outlet />;
}
interface HostListing {
  id: string;
  title: string;
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';
  suburb: string;
  state: string;
  base_nightly_price_cents: number;
}
export function HostPage() {
  const session = useSession();
  const userId =
    session.data?.state === 'authenticated' ? session.data.user.id : null;
  const listings = useQuery({
    queryKey: ['host-listings', userId],
    queryFn: ({ signal }) => get<HostListing[]>('/host/listings', signal),
    retry: false,
    meta: { private: true },
  });
  return (
    <>
      <p className="eyebrow">WELCOME HOME, HOST</p>
      <h1>Your Host workspace</h1>
      <p>
        Your Host profile is enabled. Review requests and help plan their next
        stay.
      </p>
      <Link className="button" to="/host/bookings">
        Open booking inbox
      </Link>
      <h2>Your Listings</h2>
      {listings.isPending ? (
        <p role="status">Loading Listings…</p>
      ) : listings.isError ? (
        <RequestError
          error={listings.error}
          retry={() => void listings.refetch()}
        />
      ) : !listings.data.length ? (
        <p>No Listings yet. Listing editors will follow in a later step.</p>
      ) : (
        <div className="workspace-grid">
          {listings.data.map((l) => (
            <article className="workspace-panel" key={l.id}>
              <h3>{l.title}</h3>
              <p>
                {l.suburb}, {l.state} ·{' '}
                {l.status === 'PUBLISHED'
                  ? 'Published'
                  : l.status === 'DRAFT'
                    ? 'Draft'
                    : 'Archived'}
              </p>
              <p>{aud(l.base_nightly_price_cents)} AUD / night</p>
              {l.status === 'PUBLISHED' && (
                <Link to={`/stays/${l.id}`}>View public Listing</Link>
              )}
            </article>
          ))}
        </div>
      )}
    </>
  );
}

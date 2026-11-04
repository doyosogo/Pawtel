import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { clearPrivateData, sessionKey } from '../auth/session';
import { Link, useLocation } from 'react-router';
import { ApiError, errorMessage } from '../../lib/api';
import { VerificationNotice } from './VerificationNotice';
export function RequestError({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  const location = useLocation();
  const client = useQueryClient();
  const expired = error instanceof ApiError && error.status === 401;
  useEffect(() => {
    if (expired)
      void clearPrivateData(client).then(() =>
        client.setQueryData(sessionKey, { state: 'anonymous' }),
      );
  }, [expired, client]);
  if (error instanceof ApiError && error.code === 'email_not_verified')
    return <VerificationNotice />;
  return (
    <div className="notice" role="alert">
      <p>{errorMessage(error)}</p>
      {error instanceof ApiError && error.status === 401 ? (
        <Link
          to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
        >
          Log in again
        </Link>
      ) : (
        retry && (
          <button className="button secondary small" onClick={retry}>
            Refresh
          </button>
        )
      )}
    </div>
  );
}

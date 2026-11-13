import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { setPersona, resetShowcase, type Persona } from './adapter';
import {
  clearPrivateData,
  sessionKey,
  useSession,
} from '../features/auth/session';
import { owner, host } from './fixtures';
export function ShowcaseNotice() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const session = useSession();
  const persona =
    session.data?.state === 'authenticated'
      ? session.data.user.id === host.id
        ? 'host'
        : 'owner'
      : 'visitor';
  async function explore(next: Persona, reset = false) {
    setBusy(true);
    // A persona change cancels/removes private queries before exposing the next UI.
    await clearPrivateData(client);
    client.getMutationCache().clear();
    if (reset) {
      resetShowcase();
      await client.cancelQueries();
      client.clear();
    }
    setPersona(next);
    client.setQueryData(
      sessionKey,
      next === 'visitor'
        ? { state: 'anonymous' }
        : { state: 'authenticated', user: next === 'owner' ? owner : host },
    );
    navigate(
      next === 'host' ? '/host' : next === 'owner' ? '/account/pets' : '/',
    );
    setBusy(false);
  }
  return (
    <aside className="showcase-notice" aria-label="Frontend showcase">
      <div className="container showcase-inner">
        <div>
          <strong>PAWTEL Frontend Showcase · synthetic data</strong>
          <p>
            This public demo uses synthetic data and simulated actions. No real
            bookings, accounts or payments are created. Refresh resets your
            changes.
          </p>
          <a
            href="https://github.com/doyosogo/Pawtel"
            target="_blank"
            rel="noreferrer"
          >
            Explore the full-stack implementation ↗
          </a>
        </div>
        <div
          className="showcase-personas"
          aria-label="Explore synthetic personas"
        >
          <button
            className="button small"
            disabled={busy}
            aria-pressed={persona === 'owner'}
            onClick={() => void explore('owner')}
          >
            Explore as Owner
          </button>
          <button
            className="button secondary small"
            disabled={busy}
            aria-pressed={persona === 'host'}
            onClick={() => void explore('host')}
          >
            Explore as Host
          </button>
          <button
            className="showcase-reset"
            disabled={busy}
            onClick={() => void explore('visitor', true)}
          >
            Reset showcase
          </button>
        </div>
      </div>
    </aside>
  );
}

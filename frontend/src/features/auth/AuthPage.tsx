import { useRef, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { errorMessage, write } from '../../lib/api';
import { clearPrivateData, sessionKey, useSession, type User } from './session';
import { Icon } from '../../components/Icon';

export function AuthPage({ register = false }: { register?: boolean }) {
  const session = useSession();
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const password = useRef<HTMLInputElement>(null);
  const [created, setCreated] = useState(false);
  const from = new URLSearchParams(location.search).get('next');
  const destination =
    from?.startsWith('/') && !from.startsWith('//') ? from : '/stays';
  function onSubmit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const data = {
      email: String(form.get('email')).trim(),
      password: String(form.get('password')),
      ...(register
        ? { display_name: String(form.get('display_name')).trim() }
        : {}),
    };
    if (password.current) password.current.value = '';
    // Form values stay out of React/Query state and browser storage.
    void run(data);
  }
  async function run(data: {
    email: string;
    password: string;
    display_name?: string;
  }) {
    // The password exists only in a transient request closure, not a query cache.
    const outcome = await attempt(data);
    if (outcome) {
      if (register) setCreated(true);
      else {
        await clearPrivateData(client);
        client.setQueryData(sessionKey, {
          state: 'authenticated',
          user: outcome,
        });
        await client.invalidateQueries({ queryKey: sessionKey });
        navigate(destination, { replace: true });
      }
    }
  }
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<unknown>(null);
  async function attempt(data: {
    email: string;
    password: string;
    display_name?: string;
  }): Promise<User | null> {
    setBusy(true);
    setFailure(null);
    try {
      if (register) {
        const response = await write<{
          user: User;
          verification_delivery: 'not_configured';
        }>('/auth/register', data);
        return response.user;
      }
      return await write<User>('/auth/login', data);
    } catch (error) {
      setFailure(error);
      return null;
    } finally {
      data.password = '';
      setBusy(false);
    }
  }
  // No passwords are sent through TanStack mutation variables or retained in cache.
  if (session.data?.state === 'authenticated')
    return <Navigate to={destination} replace />;
  return (
    <div className="container auth-layout">
      <div className="auth-story">
        <p className="eyebrow">A GOOD STAY STARTS HERE</p>
        <h1>
          For their next
          <br />
          little adventure.
        </h1>
        <p>
          A welcoming home for your pet. A little more peace of mind for you.
        </p>
        <img src="/media/garden.svg" alt="" />
      </div>
      <section className="auth-card" aria-labelledby="auth-title">
        {created ? (
          <div className="success-panel">
            <span className="success-mark">
              <Icon name="paw" size={30} />
            </span>
            <h1 id="auth-title">You’re part of PAWTEL.</h1>
            <p>
              Account created. Email delivery is not configured in this demo
              yet, so no verification email has been sent.
            </p>
            <p>
              You can sign in and explore. Hosting and bookings require verified
              email.
            </p>
            <Link
              className="button"
              to={`/login?next=${encodeURIComponent(destination)}`}
            >
              Continue to log in
            </Link>
          </div>
        ) : (
          <>
            <p className="eyebrow">
              WELCOME {register ? 'TO' : 'BACK TO'} PAWTEL
            </p>
            <h1 id="auth-title">
              {register ? 'Make yourself at home.' : 'Good to see you again.'}
            </h1>
            <p className="muted">
              {register
                ? 'Create an account for you and your favourite companion.'
                : 'Log in to your PAWTEL account.'}
            </p>
            {session.data?.state === 'inactive' && (
              <p className="notice" role="alert">
                Your account is inactive. You can log out from the account menu.
              </p>
            )}
            <form
              onSubmit={onSubmit}
              className="stack"
              aria-describedby={failure ? 'auth-error' : undefined}
            >
              {register && (
                <label className="field">
                  Your name
                  <input
                    name="display_name"
                    autoComplete="name"
                    required
                    maxLength={100}
                    pattern={String.raw`.*\S.*`}
                  />
                </label>
              )}
              <label className="field">
                Email address
                <input
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  maxLength={254}
                />
              </label>
              <label className="field">
                Password
                <input
                  ref={password}
                  name="password"
                  type="password"
                  autoComplete={register ? 'new-password' : 'current-password'}
                  minLength={register ? 15 : 1}
                  maxLength={128}
                  required
                  aria-describedby={register ? 'password-help' : undefined}
                />
              </label>
              {register && (
                <p className="field-help" id="password-help">
                  Use 15–128 characters. A memorable passphrase works well.
                </p>
              )}
              {failure != null && (
                <p className="error-text" id="auth-error" role="alert">
                  {errorMessage(failure)}
                </p>
              )}
              <button
                className="button"
                disabled={busy || session.isPending}
                type="submit"
              >
                {busy ? 'One moment…' : register ? 'Create account' : 'Log in'}
              </button>
            </form>
            <p className="auth-switch">
              {register ? 'Already have an account?' : 'New to PAWTEL?'}{' '}
              <Link
                to={`${register ? '/login' : '/register'}?next=${encodeURIComponent(destination)}`}
              >
                {register ? 'Log in' : 'Create an account'}
              </Link>
            </p>
          </>
        )}
      </section>
    </div>
  );
}

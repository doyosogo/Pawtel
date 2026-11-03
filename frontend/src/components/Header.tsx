import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  clearPrivateData,
  sessionKey,
  useHostProfile,
  useSession,
} from '../features/auth/session';
import { errorMessage, write } from '../lib/api';
import { Icon } from './Icon';

export function Header() {
  const session = useSession();
  const host = useHostProfile(session.data);
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();
  const client = useQueryClient();
  useEffect(() => {
    const outside = (event: PointerEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        toggle.current?.focus();
      }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, []);
  const logout = useMutation({
    mutationFn: () => write<void>('/auth/logout'),
    onSuccess: async () => {
      await clearPrivateData(client);
      client.setQueryData(sessionKey, { state: 'anonymous' });
      setOpen(false);
      navigate('/');
    },
  });
  const user =
    session.data?.state === 'authenticated' ? session.data.user : null;
  const hostingLabel = host.data
    ? 'Your host space'
    : user && (!user.email_verified_at || host.isPending || host.isError)
      ? 'Hosting'
      : 'Become a host';
  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link className="brand" to="/" aria-label="PAWTEL home">
          <span className="brand-mark">
            <Icon name="paw" size={27} />
          </span>
          pawtel<span className="brand-dot">.</span>
        </Link>
        <nav className="primary-nav" aria-label="Main navigation">
          <NavLink to="/stays">Find a stay</NavLink>
          <NavLink to="/hosting">For hosts</NavLink>
        </nav>
        <div className="header-actions">
          <Link className="host-link" to="/hosting">
            {hostingLabel}
          </Link>
          <div className="account-control" ref={wrapper}>
            <button
              className="account-toggle"
              ref={toggle}
              aria-label="Account menu"
              aria-expanded={open}
              aria-controls="account-menu"
              onClick={() => setOpen(!open)}
            >
              <Icon name="menu" size={18} />
              <span className="avatar">
                {session.isPending ? (
                  <span className="loading-dot" />
                ) : user ? (
                  user.display_name.slice(0, 1).toUpperCase()
                ) : (
                  <Icon name="user" size={18} />
                )}
              </span>
            </button>
            {open && (
              <div className="account-popover" id="account-menu">
                {session.isPending ? (
                  <p role="status">Checking your session…</p>
                ) : session.isError ? (
                  <>
                    <p role="alert">We couldn’t check your session.</p>
                    <button onClick={() => void session.refetch()}>
                      Try again
                    </button>
                  </>
                ) : user || session.data?.state === 'inactive' ? (
                  <>
                    <p className="menu-greeting">
                      {user
                        ? `Hello, ${user.display_name}`
                        : 'Account inactive'}
                    </p>
                    {user && (
                      <Link to="/account" onClick={() => setOpen(false)}>
                        Your account
                      </Link>
                    )}
                    <Link to="/hosting" onClick={() => setOpen(false)}>
                      {hostingLabel}
                    </Link>
                    <button
                      disabled={logout.isPending}
                      onClick={() => logout.mutate()}
                    >
                      {logout.isPending ? 'Signing out…' : 'Log out'}
                    </button>
                    {logout.isError && (
                      <p className="error-text" role="alert">
                        {errorMessage(logout.error)}
                      </p>
                    )}
                  </>
                ) : (
                  <>
                    <Link to="/login" onClick={() => setOpen(false)}>
                      Log in
                    </Link>
                    <Link
                      to="/register"
                      className="menu-signup"
                      onClick={() => setOpen(false)}
                    >
                      Create an account
                    </Link>
                    <Link to="/hosting" onClick={() => setOpen(false)}>
                      Explore hosting
                    </Link>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

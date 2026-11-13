import { SHOWCASE } from '../showcase/mode';
import { lazy, Suspense } from 'react';
import { Outlet, useLocation } from 'react-router';
import { useEffect } from 'react';
import { DemoNotice } from '../components/DemoNotice';
import { Header } from '../components/Header';
import { Footer } from '../components/Footer';
const ShowcaseNotice = lazy(() =>
  import('../showcase/ShowcaseNotice').then((module) => ({
    default: module.ShowcaseNotice,
  })),
);
export function Layout() {
  const location = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [location.pathname]);
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <Header />
      {SHOWCASE ? (
        <Suspense fallback={null}>
          <ShowcaseNotice />
        </Suspense>
      ) : (
        <DemoNotice />
      )}
      <main id="main-content">
        <Outlet />
      </main>
      <Footer />
    </>
  );
}

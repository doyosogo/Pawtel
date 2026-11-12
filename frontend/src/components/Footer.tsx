import { Link } from 'react-router';
export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <div>
          <Link className="footer-brand" to="/">
            pawtel.
          </Link>
          <p>A little holiday for them, too.</p>
        </div>
        <p className="demo-disclosure">
          Portfolio demo · Seed hosts and stays are fictional.
          <br />
          Listings without photos use labelled demo illustrations.
        </p>
        <nav aria-label="Footer">
          <Link to="/stays">Explore stays</Link>
          <Link to="/hosting">Hosting</Link>
        </nav>
      </div>
      <div className="container footer-bottom">
        Made for dogs, cats & the people who love them.{' '}
        <span>Australia · AUD</span>
      </div>
    </footer>
  );
}

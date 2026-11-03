import { Link } from 'react-router';
export function NotFoundPage() {
  return (
    <div className="container feedback">
      <p className="eyebrow">A LITTLE OFF THE PATH</p>
      <h1>We couldn’t find that page.</h1>
      <p>Let’s get you back to somewhere welcoming.</p>
      <Link className="button" to="/stays">
        Explore stays
      </Link>
    </div>
  );
}

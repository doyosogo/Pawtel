import { Link } from 'react-router';
import { SearchBar } from '../features/listings/SearchBar';
import { Results } from '../features/listings/Results';
import { Icon } from '../components/Icon';

export function HomePage() {
  return (
    <>
      <section className="home-intro container">
        <div className="hero-copy">
          <p className="eyebrow">THEIR STAY. YOUR PEACE OF MIND.</p>
          <h1>
            A little holiday
            <br />
            for <em>them</em>, too.
          </h1>
          <p>
            Find a welcoming home for your dog or cat
            <br className="desktop-break" /> while you’re away.
          </p>
          <div className="hero-caption">
            <span>
              <Icon name="paw" size={17} />
            </span>{' '}
            Good company is closer than you think.
          </div>
        </div>
        <div className="hero-art">
          <img src="/media/sunroom.svg" alt="" />
          <span className="hero-note">
            More belly rubs.
            <br />
            Less missing you.<span aria-hidden="true">♡</span>
          </span>
        </div>
      </section>
      <div className="container home-search">
        <SearchBar />
      </div>
      <section
        className="container results-section"
        aria-labelledby="results-heading"
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">A PLACE TO FEEL AT HOME</p>
            <h2 id="results-heading" tabIndex={-1}>
              Stays for your favourite companion
            </h2>
          </div>
          <span className="section-aside">Dogs, cats & warm welcomes</span>
        </div>
        <nav
          className="discovery-chips"
          aria-label="Explore by pet or location"
        >
          <Link className="active" to="/stays">
            All stays
          </Link>
          <Link to="/stays?species=DOG">Dogs welcome</Link>
          <Link to="/stays?species=CAT">Cats welcome</Link>
          <Link to="/stays?species=DOG&species=CAT">Dogs & cats</Link>
          <Link to="/stays?state=SA">Adelaide & South Australia</Link>
        </nav>
        <Results home />
      </section>
      <section className="container host-banner">
        <div>
          <p className="eyebrow">MAKE ROOM FOR A LITTLE JOY</p>
          <h2>Your home. Their happy place.</h2>
          <p>Discover what hosting on PAWTEL could look like.</p>
          <Link className="button secondary" to="/hosting">
            Explore hosting <Icon name="arrow" size={17} />
          </Link>
        </div>
        <div className="host-banner-art" aria-hidden="true">
          <Icon name="paw" size={96} />
          <span>
            More paws.
            <br />
            More possibility.
          </span>
        </div>
      </section>
    </>
  );
}

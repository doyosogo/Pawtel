import { useSearchParams } from 'react-router';
import { Results } from '../features/listings/Results';
import { SearchBar } from '../features/listings/SearchBar';
import { aud } from '../features/listings/api';
import { whereLabel } from '../features/listings/search';

export function StaysPage() {
  const [params, setParams] = useSearchParams();
  const where = whereLabel(params);
  function prices(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const next = new URLSearchParams(params);
    for (const key of ['min_price_cents', 'max_price_cents']) {
      const amount = String(data.get(key) ?? '');
      if (amount) next.set(key, String(Math.round(Number(amount) * 100)));
      else next.delete(key);
    }
    next.delete('offset');
    setParams(next);
  }
  const summary = [
    params
      .getAll('species')
      .map((s) => (s === 'DOG' ? 'Dogs' : s === 'CAT' ? 'Cats' : s))
      .join(' + '),
    params.get('check_in') && params.get('check_out')
      ? `${params.get('check_in')} → ${params.get('check_out')}`
      : 'Flexible dates',
    params.get('pet_count')
      ? `${params.get('pet_count')} pet${params.get('pet_count') === '1' ? '' : 's'}`
      : '',
    params.get('max_price_cents')
      ? `Up to ${aud(Number(params.get('max_price_cents')))}/night`
      : '',
  ]
    .filter(Boolean)
    .join(' · ');
  return (
    <div className="container stays-page">
      <div className="page-intro">
        <p className="eyebrow">GOOD HOMES. HAPPY COMPANIONS.</p>
        <h1>
          {where ? `Stays in ${where}` : 'Find their home away from home.'}
        </h1>
        <p>Pet boarding across Australia, one warm welcome at a time.</p>
      </div>
      <SearchBar key={params.toString()} initial={params} />
      <section className="results-section" aria-labelledby="results-heading">
        <div className="results-toolbar">
          <div>
            <h2 id="results-heading" tabIndex={-1}>
              Explore stays
            </h2>
            <p className="muted">{summary}</p>
          </div>
          <details className="price-filter">
            <summary>Price filters</summary>
            <form onSubmit={prices} className="stack" key={params.toString()}>
              <p className="field-help">
                Base nightly rate in Australian dollars.
              </p>
              <label className="field">
                Minimum AUD
                <input
                  name="min_price_cents"
                  type="number"
                  min={0}
                  step={0.01}
                  defaultValue={
                    params.has('min_price_cents')
                      ? Number(params.get('min_price_cents')) / 100
                      : ''
                  }
                />
              </label>
              <label className="field">
                Maximum AUD
                <input
                  name="max_price_cents"
                  type="number"
                  min={0}
                  step={0.01}
                  defaultValue={
                    params.has('max_price_cents')
                      ? Number(params.get('max_price_cents')) / 100
                      : ''
                  }
                />
              </label>
              <button className="button small" type="submit">
                Apply prices
              </button>
            </form>
          </details>
        </div>
        <Results />
      </section>
    </div>
  );
}

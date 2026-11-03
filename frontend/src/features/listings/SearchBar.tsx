import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Icon } from '../../components/Icon';
import {
  localToday,
  locationParams,
  nextDay,
  validStay,
  whereLabel,
} from './search';

export function SearchBar({
  initial = new URLSearchParams(),
}: {
  initial?: URLSearchParams;
}) {
  const navigate = useNavigate();
  const [where, setWhere] = useState(whereLabel(initial));
  const [start, setStart] = useState(initial.get('check_in') ?? '');
  const [end, setEnd] = useState(initial.get('check_out') ?? '');
  const [species, setSpecies] = useState(initial.getAll('species'));
  const [count, setCount] = useState(initial.get('pet_count') ?? '1');
  const [error, setError] = useState('');
  function search(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if ((start || end) && !validStay(start, end)) {
      setError('Choose both dates, with checkout after check-in.');
      return;
    }
    const params = locationParams(where);
    params.set('pet_count', count);
    if (start) {
      params.set('check_in', start);
      params.set('check_out', end);
    }
    species.forEach((value) => params.append('species', value));
    navigate(`/stays?${params}`);
  }
  return (
    <form className="search-panel" onSubmit={search} aria-label="Search stays">
      <div className="search-fields">
        <label className="where-field">
          Where
          <input
            value={where}
            onChange={(e) => setWhere(e.target.value)}
            placeholder="Suburb, postcode or state"
            maxLength={100}
          />
        </label>
        <label>
          Check in
          <input
            type="date"
            value={start}
            min={localToday()}
            required={!!end}
            onChange={(e) => {
              setStart(e.target.value);
              if (end <= e.target.value) setEnd('');
            }}
          />
        </label>
        <label>
          Check out
          <input
            type="date"
            value={end}
            min={start ? nextDay(start) : localToday()}
            required={!!start}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <label className="count-field">
          Pets
          <input
            type="number"
            value={count}
            min={1}
            max={2147483647}
            required
            onChange={(e) => setCount(e.target.value)}
          />
        </label>
        <button
          className="button search-button"
          type="submit"
          aria-label="Search stays"
        >
          <Icon name="search" /> <span>Search</span>
        </button>
      </div>
      <div className="search-bottom">
        <fieldset className="species-options">
          <legend>Travelling with</legend>
          {(['DOG', 'CAT'] as const).map((value) => (
            <label
              key={value}
              className={
                species.includes(value)
                  ? 'species-chip selected'
                  : 'species-chip'
              }
            >
              <input
                type="checkbox"
                checked={species.includes(value)}
                onChange={(e) =>
                  setSpecies(
                    e.target.checked
                      ? [...species, value]
                      : species.filter((s) => s !== value),
                  )
                }
              />
              {value === 'DOG' ? 'Dogs' : 'Cats'}
            </label>
          ))}
        </fieldset>
        <span className="search-hint">Boarding stays, Australia-wide</span>
      </div>
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}

import { describe, expect, it } from 'vitest';
import { apiSearch, locationParams, nextDay, validStay } from './search';
import { aud } from './api';
describe('discovery contract', () => {
  it('maps only the backend textual location fields', () => {
    expect(locationParams(' sa ').toString()).toBe('state=SA');
    expect(locationParams('0800').toString()).toBe('postcode=0800');
    expect(locationParams(' Glenelg ').toString()).toBe('suburb=Glenelg');
  });
  it('preserves ALL-species repetition and filters URL noise', () => {
    const params = apiSearch(
      new URLSearchParams('species=DOG&species=CAT&suburb=Norwood&tracking=x'),
    );
    expect(params.getAll('species')).toEqual(['DOG', 'CAT']);
    expect(params.has('tracking')).toBe(false);
    expect(params.get('limit')).toBe('8');
  });
  it('requires strictly ordered dates and handles month boundaries', () => {
    expect(validStay('2027-11-10', '2027-11-10')).toBe(false);
    expect(validStay('2027-11-12', '2027-11-10')).toBe(false);
    expect(validStay('2027-11-10', '2027-11-12')).toBe(true);
    expect(nextDay('2028-02-29')).toBe('2028-03-01');
  });
  it('formats AUD cents without losing decimal values', () => {
    expect(aud(5200)).toBe('$52');
    expect(aud(5250)).toBe('$52.50');
    expect(aud(0)).toBe('$0');
  });
});
it('rejects malformed and impossible calendar dates', () => {
  expect(validStay('2028-02-30', '2028-03-02')).toBe(false);
  expect(validStay('not-a-date', 'tomorrow')).toBe(false);
  expect(validStay('', '2028-03-02')).toBe(false);
  expect(validStay('2028-02-29', '2028-03-01')).toBe(true);
});

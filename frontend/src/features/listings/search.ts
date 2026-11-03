export const states = ['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA'];
const allowed = [
  'state',
  'suburb',
  'postcode',
  'species',
  'min_price_cents',
  'max_price_cents',
  'pet_count',
  'check_in',
  'check_out',
  'limit',
  'offset',
];
export function apiSearch(input: URLSearchParams) {
  const result = new URLSearchParams();
  for (const [key, value] of input)
    if (allowed.includes(key)) result.append(key, value);
  if (!result.has('limit')) result.set('limit', '8');
  return result;
}
export function whereLabel(params: URLSearchParams) {
  return (
    params.get('suburb') ?? params.get('postcode') ?? params.get('state') ?? ''
  );
}
export function locationParams(where: string) {
  const result = new URLSearchParams();
  const value = where.trim();
  if (states.includes(value.toUpperCase()))
    result.set('state', value.toUpperCase());
  else if (/^\d{4}$/.test(value)) result.set('postcode', value);
  else if (value) result.set('suburb', value);
  return result;
}
export function nextDay(value: string) {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
export function localToday() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
export function validStay(start: string, end: string) {
  const isDate = (value: string) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(`${value}T00:00:00Z`);
    return (
      !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value
    );
  };
  return isDate(start) && isDate(end) && end > start;
}

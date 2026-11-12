import { get } from '../../lib/api';
export type Species = 'DOG' | 'CAT';
export interface ListingImage {
  id: string;
  url: string;
  alt_text: string;
  sort_order: number;
}
export interface Listing {
  images?: ListingImage[];
  id: string;
  title: string;
  description: string;
  suburb: string;
  state: string;
  postcode: string;
  country_code: string;
  base_nightly_price_cents: number;
  additional_pet_price_cents: number;
  max_pet_capacity: number;
  accepted_species: Species[];
  host: { display_name: string; bio: string | null };
}
export interface ListingPage {
  items: Listing[];
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
}
export interface Availability {
  listing_id: string;
  check_in: string;
  check_out: string;
  pet_count: number;
  available: boolean;
  remaining_capacity_at_tightest_point: number;
}
export const listings = (params: URLSearchParams, signal?: AbortSignal) =>
  get<ListingPage>(`/listings?${params}`, signal);
export const listingDetail = (id: string, signal?: AbortSignal) =>
  get<Listing>(`/listings/${encodeURIComponent(id)}`, signal);
export const listingAvailability = (
  id: string,
  params: URLSearchParams,
  signal?: AbortSignal,
) =>
  get<Availability>(
    `/listings/${encodeURIComponent(id)}/availability?${params}`,
    signal,
  );
export function aud(cents: number) {
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: cents % 100 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

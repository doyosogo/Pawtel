import { useQuery, useQueryClient } from '@tanstack/react-query';
import { get, write } from '../../lib/api';
import { useSession } from '../auth/session';
import type { Listing, ListingImage } from '../listings/api';
export interface HostListing extends Omit<Listing, 'host'> {
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';
  created_at: string;
  updated_at: string;
}
export type ListingInput = Pick<
  HostListing,
  | 'title'
  | 'description'
  | 'suburb'
  | 'state'
  | 'postcode'
  | 'max_pet_capacity'
  | 'base_nightly_price_cents'
  | 'additional_pet_price_cents'
  | 'accepted_species'
>;
export function useHostListings(id?: string, status = '', enabled = true) {
  const session = useSession();
  const uid =
    session.data?.state === 'authenticated' ? session.data.user.id : null;
  return useQuery({
    queryKey: ['host-listings', uid, id ?? 'collection', status],
    queryFn: ({ signal }) =>
      get<HostListing | HostListing[]>(
        `/host/listings${id ? `/${encodeURIComponent(id)}` : status ? `?status=${status}` : ''}`,
        signal,
      ),
    enabled: !!uid && enabled,
    retry: false,
    meta: { private: true },
  });
}
export const saveListing = (input: Partial<ListingInput>, id?: string) =>
  write<HostListing>(
    `/host/listings${id ? `/${encodeURIComponent(id)}` : ''}`,
    input,
    id ? 'PATCH' : 'POST',
  );
export function useRefreshHost() {
  const client = useQueryClient();
  return async () => {
    await Promise.all(
      ['host-listings', 'host-profile', 'listing', 'listings'].map((key) =>
        client.invalidateQueries({ queryKey: [key] }),
      ),
    );
  };
}
export const imageOrder = (id: string, images: ListingImage[]) =>
  write<ListingImage[]>(
    `/host/listings/${id}/images/order`,
    { image_ids: images.map((image) => image.id) },
    'PATCH',
  );

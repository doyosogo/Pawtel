import { useQuery } from '@tanstack/react-query';
import { get, write } from '../../lib/api';
import { useSession } from '../auth/session';
import type { Species } from '../listings/api';
export interface Pet {
  id: string;
  name: string;
  species: Species;
  breed: string | null;
  date_of_birth: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export type PetInput = Pick<
  Pet,
  'name' | 'species' | 'breed' | 'date_of_birth'
>;
export function usePets(includeArchived = false) {
  const session = useSession();
  const user =
    session.data?.state === 'authenticated' ? session.data.user : null;
  return useQuery({
    queryKey: ['pets', user?.id, includeArchived],
    queryFn: ({ signal }) =>
      get<Pet[]>(`/pets?include_archived=${includeArchived}`, signal),
    enabled: !!user,
    retry: false,
    meta: { private: true },
  });
}
export const savePet = (data: PetInput, id?: string) =>
  write<Pet>(
    id ? `/pets/${encodeURIComponent(id)}` : '/pets',
    data,
    id ? 'PATCH' : 'POST',
  );
export const archivePet = (id: string) =>
  write<void>(`/pets/${encodeURIComponent(id)}`, {}, 'DELETE');

import { useQuery, type QueryClient } from '@tanstack/react-query';
import { ApiError, get } from '../../lib/api';

export interface User {
  id: string;
  email: string;
  display_name: string;
  email_verified_at: string | null;
  is_active: boolean;
  created_at: string;
}
export type Session =
  | { state: 'anonymous' }
  | { state: 'inactive' }
  | { state: 'authenticated'; user: User };
export const sessionKey = ['session'] as const;
export function useSession() {
  return useQuery({
    queryKey: sessionKey,
    queryFn: async ({ signal }): Promise<Session> => {
      try {
        return {
          state: 'authenticated',
          user: await get<User>('/auth/me', signal),
        };
      } catch (error) {
        if (error instanceof ApiError && error.status === 401)
          return { state: 'anonymous' };
        if (error instanceof ApiError && error.code === 'account_inactive')
          return { state: 'inactive' };
        throw error;
      }
    },
    staleTime: 30_000,
    retry: false,
    meta: { private: true },
  });
}
export async function clearPrivateData(client: QueryClient) {
  await client.cancelQueries({
    predicate: (query) => query.meta?.private === true,
  });
  // Keep the observed session query so setting anonymous/current-user notifies every subscriber.
  client.removeQueries({
    predicate: (query) =>
      query.meta?.private === true && query.queryKey[0] !== sessionKey[0],
  });
}
export interface HostProfile {
  user_id: string;
  bio: string | null;
  created_at: string;
  updated_at: string;
}
export function useHostProfile(session: Session | undefined) {
  return useQuery({
    queryKey: [
      'host-profile',
      session?.state === 'authenticated' ? session.user.id : null,
    ],
    queryFn: async ({ signal }) => {
      try {
        return await get<HostProfile>('/host/profile', signal);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    enabled:
      session?.state === 'authenticated' && !!session.user.email_verified_at,
    retry: false,
    meta: { private: true },
  });
}

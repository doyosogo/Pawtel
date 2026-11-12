import { useQuery } from '@tanstack/react-query';
import { get } from '../../lib/api';
export interface PublicConfig {
  portfolio_demo: boolean;
  registration_enabled: boolean;
}
export function usePublicConfig(enabled = true) {
  return useQuery({
    queryKey: ['public-config'],
    queryFn: () => get<PublicConfig>('/config'),
    enabled,
    staleTime: 60_000,
    retry: false,
  });
}

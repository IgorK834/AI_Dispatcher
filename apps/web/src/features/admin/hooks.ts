'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { unwrap } from '@/lib/api/unwrap';

export type CostProfile = components['schemas']['CostProfileView'];

export function useCostProfiles() {
  return useQuery({
    queryKey: ['cost-profiles'],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/cost-profiles', { params: { query: { limit: 20 } } })).items,
  });
}

/** The AI status of the server (the same query the AI Dispatcher uses). */
export function useAiStatus() {
  return useQuery({
    queryKey: ['agent-status'],
    staleTime: 30_000,
    retry: false,
    queryFn: async () => unwrap(await api.GET('/api/v1/agent/status')),
  });
}

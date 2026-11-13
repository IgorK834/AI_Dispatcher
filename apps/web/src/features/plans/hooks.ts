'use client';

import { useMutation, useQueries, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { unwrap } from '@/lib/api/unwrap';
import type { Objective, PlanSummary, RoutePlan } from './types';
import { OBJECTIVES } from './types';

export function usePlan(planId: string) {
  return useQuery({
    queryKey: ['plan', planId],
    queryFn: async (): Promise<RoutePlan> =>
      unwrap(
        await api.GET('/api/v1/route-plans/{plan_id}', { params: { path: { plan_id: planId } } }),
      ),
  });
}

/** The driver, with the embedded van: the load plan and the vehicle card need its layout. */
export function useDriverOfPlan(driverId: string | undefined) {
  return useQuery({
    queryKey: ['driver', driverId],
    enabled: driverId !== undefined,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/drivers/{driver_id}', {
          params: { path: { driver_id: driverId as string } },
        }),
      ),
  });
}

/** The rank 1 plan of each objective for one driver, from the job result named by `?job=`. */
export function useJobVariants(jobId: string | null, driverId: string | undefined) {
  return useQuery({
    queryKey: ['job-result', jobId],
    enabled: jobId !== null && driverId !== undefined,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/optimization-jobs/{job_id}/result', {
          params: { path: { job_id: jobId as string } },
        }),
      ),
    select: (result) => {
      const plans = result.perDriver.find((entry) => entry.driverId === driverId)?.plans ?? {};
      const variants: Partial<Record<Objective, PlanSummary>> = {};
      for (const objective of OBJECTIVES) {
        const first = plans[objective]?.[0];
        if (first) variants[objective] = first;
      }
      return variants;
    },
  });
}

/** Source ids of the offers on a plan (TC-1001) by offer id; missing until loaded. */
export function useOfferNames(offerIds: string[]) {
  const results = useQueries({
    queries: offerIds.map((offerId) => ({
      queryKey: ['offer', offerId],
      staleTime: 60_000,
      queryFn: async () =>
        unwrap(
          await api.GET('/api/v1/freight-offers/{offer_id}', {
            params: { path: { offer_id: offerId } },
          }),
        ),
    })),
  });
  const names: Record<string, string> = {};
  results.forEach((result, index) => {
    const id = offerIds[index];
    if (id && result.data) names[id] = result.data.sourceOfferId;
  });
  return names;
}

export function useExplain(planId: string) {
  return useMutation({
    mutationFn: async (locale: 'en' | 'pl') =>
      unwrap(
        await api.POST('/api/v1/route-plans/{plan_id}/explanations', {
          params: { path: { plan_id: planId } },
          body: { locale },
        }),
      ),
  });
}

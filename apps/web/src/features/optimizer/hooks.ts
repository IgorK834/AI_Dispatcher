'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { unwrap } from '@/lib/api/unwrap';

export type Job = components['schemas']['Job'];
export type JobCreate = components['schemas']['JobCreate'];
export type JobResult = components['schemas']['JobResult'];
export type FleetSolution = components['schemas']['FleetSolution'];
export type PlanSummary = components['schemas']['PlanSummary'];
export type Objective = 'profit' | 'fastest' | 'fuel';
export const OBJECTIVES: Objective[] = ['profit', 'fastest', 'fuel'];

const TERMINAL = new Set(['succeeded', 'failed', 'cancelled']);
export const POLL_MS = 1000;

/** A fresh Idempotency-Key per click: a double click cannot start two runs. */
export function useStartJob() {
  return useMutation({
    mutationFn: async (body: JobCreate): Promise<Job> =>
      unwrap(
        await api.POST('/api/v1/optimization-jobs', {
          body,
          params: { header: { 'Idempotency-Key': crypto.randomUUID() } },
        }),
      ),
  });
}

/** Polls the job once a second until it ends. */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ['job', jobId],
    enabled: jobId !== null,
    refetchInterval: (query) =>
      query.state.data && TERMINAL.has(query.state.data.status) ? false : POLL_MS,
    queryFn: async (): Promise<Job> =>
      unwrap(
        await api.GET('/api/v1/optimization-jobs/{job_id}', {
          params: { path: { job_id: jobId as string } },
        }),
      ),
  });
}

export function useJobResult(jobId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ['job-result', jobId],
    enabled: jobId !== null && enabled,
    queryFn: async (): Promise<JobResult> =>
      unwrap(
        await api.GET('/api/v1/optimization-jobs/{job_id}/result', {
          params: { path: { job_id: jobId as string } },
        }),
      ),
  });
}

/** Drivers for the form's driver list and for naming rows of the result. */
export function useDriverDirectory() {
  return useQuery({
    queryKey: ['drivers', 'directory'],
    staleTime: 30_000,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/drivers', { params: { query: { limit: 100 } } })).items,
  });
}

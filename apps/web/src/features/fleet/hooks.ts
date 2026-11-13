'use client';

import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { unwrap } from '@/lib/api/unwrap';

export type Driver = components['schemas']['DriverView'];
export type Vehicle = components['schemas']['VehicleView'];
export type CostProfile = components['schemas']['CostProfileView'];

export type DriverFilters = {
  homeCity?: string;
  availableBefore?: string;
  hasVehicle?: boolean;
};

const PAGE = 20;

/** Cursor-paginated drivers; the filters are part of the cache key, so each view is cached. */
export function useDrivers(filters: DriverFilters) {
  return useInfiniteQuery({
    queryKey: ['drivers', filters],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/v1/drivers', {
          params: {
            query: {
              limit: PAGE,
              cursor: pageParam,
              homeCity: filters.homeCity || undefined,
              availableBefore: filters.availableBefore || undefined,
              hasVehicle: filters.hasVehicle || undefined,
            },
          },
        }),
      ),
    getNextPageParam: (last) => last.nextCursor ?? undefined,
  });
}

export function useVehicles() {
  return useInfiniteQuery({
    queryKey: ['vehicles'],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/v1/vehicles', {
          params: { query: { limit: PAGE, cursor: pageParam } },
        }),
      ),
    getNextPageParam: (last) => last.nextCursor ?? undefined,
  });
}

/** All cost profiles of the first page: the vehicle form needs them for its select. */
export function useCostProfiles() {
  return useQuery({
    queryKey: ['cost-profiles'],
    staleTime: 60_000,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/cost-profiles', { params: { query: { limit: 100 } } })).items,
  });
}

/** Ids of drivers with an active assignment, for the Free/Assigned status and the KPI cards. */
export function useAssignedDriverIds() {
  return useQuery({
    queryKey: ['assignments', 'active'],
    queryFn: async () => {
      const page = unwrap(
        await api.GET('/api/v1/assignments', {
          params: { query: { status: 'active', limit: 100 } },
        }),
      );
      return new Set(page.items.map((assignment) => assignment.driverId));
    },
  });
}

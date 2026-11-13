'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { unwrap } from '@/lib/api/unwrap';

export type Offer = components['schemas']['FreightOfferView'];
export type OfferStop = components['schemas']['StopView'];

/** The value of `source` for offers that come from the demo provider (not user-entered). */
export const IMPORTED_SOURCE = 'mock_timocom_v3';
export const MANUAL_SOURCE = 'manual';

/** Filters as the API takes them; the URL carries the same values (FR-6). */
export type OfferFilters = {
  source?: string;
  originCountry?: string;
  destinationCountry?: string;
  originCity?: string;
  destinationCity?: string;
  pickupFrom?: string;
  pickupTo?: string;
  maxWeightKg?: number;
  maxPallets?: number;
  /** 0 to 1, as the API takes it; the form shows a percentage. */
  minCompleteness?: number;
  hasPrice?: boolean;
};

const PAGE = 20;

/** Cursor-paginated offers; the filters are part of the cache key. */
export function useOffers(filters: OfferFilters) {
  return useInfiniteQuery({
    queryKey: ['offers', filters],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/v1/freight-offers', {
          params: { query: { limit: PAGE, cursor: pageParam, ...filters } },
        }),
      ),
    getNextPageParam: (last) => last.nextCursor ?? undefined,
  });
}

export const isManual = (offer: Offer) => offer.source === MANUAL_SOURCE;

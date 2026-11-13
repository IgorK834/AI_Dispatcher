import type { OfferFilters } from './hooks';

const number = (value: string | null): number | undefined => {
  if (value === null || value.trim() === '') return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
};

const text = (value: string | null): string | undefined => value?.trim() || undefined;

export function filtersFromSearch(search: URLSearchParams): OfferFilters {
  const completeness = number(search.get('minCompleteness'));
  return {
    source: text(search.get('source')),
    originCountry: text(search.get('originCountry')),
    destinationCountry: text(search.get('destinationCountry')),
    originCity: text(search.get('originCity')),
    destinationCity: text(search.get('destinationCity')),
    pickupFrom: text(search.get('pickupFrom')),
    pickupTo: text(search.get('pickupTo')),
    maxWeightKg: number(search.get('maxWeightKg')),
    maxPallets: number(search.get('maxPallets')),
    minCompleteness: completeness === undefined ? undefined : Math.min(completeness, 1),
    hasPrice: search.get('hasPrice') === 'true' ? true : undefined,
  };
}

export const hasActiveFilters = (filters: OfferFilters) =>
  Object.values(filters).some((value) => value !== undefined);

import { numberFormat, type AppLocale } from './locale';

type DistanceStyle = 'list' | 'detail';

/** Whole kilometres in lists ("625 km"), one decimal in details ("624.8 km"). */
export function formatDistance(
  km: number,
  locale: AppLocale,
  style: DistanceStyle = 'list',
): string {
  const digits = style === 'list' ? 0 : 1;
  const value = numberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(km);
  return `${value} km`;
}

export function formatMass(kg: number, locale: AppLocale): string {
  return `${numberFormat(locale, { maximumFractionDigits: 0 }).format(kg)} kg`;
}

/** Pallet equivalents with one decimal: "6.0 / 10 EP" (EP stays untranslated). */
export function formatPalletEquivalents(used: number, places: number, locale: AppLocale): string {
  const one = numberFormat(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${one.format(used)} / ${numberFormat(locale, { maximumFractionDigits: 0 }).format(places)} EP`;
}

/** Litres with one decimal; callers add the word "estimate" next to it. */
export function formatFuel(litres: number, locale: AppLocale): string {
  return `${numberFormat(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(litres)} l`;
}

export function formatCo2(kg: number, locale: AppLocale): string {
  return `${numberFormat(locale, { maximumFractionDigits: 0 }).format(kg)} kg CO₂`;
}

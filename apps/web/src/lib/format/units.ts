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

/**
 * A share of 0 … 1 as a whole percentage: "46%" in English, "46 %" (no-break space) in Polish.
 * The sign is placed here because the ICU data of the runtime decides the Polish spacing otherwise.
 */
export function formatPercent(share: number, locale: AppLocale): string {
  const value = numberFormat(locale, { maximumFractionDigits: 0 }).format(share * 100);
  return locale === 'pl' ? `${value}\u00a0%` : `${value}%`;
}

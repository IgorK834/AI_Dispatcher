import { numberFormat } from '@/lib/format/locale';
import type { AppLocale } from '@/lib/format';

/** Step durations: "120 ms" below a second, "1.4 s" above. */
export function formatStepDuration(ms: number, locale: AppLocale): string {
  if (ms < 1000) return `${numberFormat(locale, { maximumFractionDigits: 0 }).format(ms)} ms`;
  return `${numberFormat(locale, { maximumFractionDigits: 1 }).format(ms / 1000)} s`;
}

export function formatTokens(tokens: number, locale: AppLocale): string {
  return numberFormat(locale, { maximumFractionDigits: 0 }).format(tokens);
}

/** The API sends litres and kilograms as decimal strings. */
export const toNumber = (value: string): number => Number.parseFloat(value);

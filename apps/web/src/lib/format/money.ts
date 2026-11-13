import { numberFormat, type AppLocale } from './locale';

/** `minor` is an integer in minor units (cents); 123450 EUR is "€1,234.50" / "1 234,50 €". */
export function formatMoney(minor: number, currency: string, locale: AppLocale): string {
  return numberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(minor / 100);
}

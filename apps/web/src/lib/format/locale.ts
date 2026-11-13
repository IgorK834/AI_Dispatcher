export type AppLocale = 'en' | 'pl';

/** BCP 47 tags used for all number and date formatting. */
export function intlTag(locale: AppLocale): string {
  return locale === 'pl' ? 'pl-PL' : 'en-US';
}

export function numberFormat(
  locale: AppLocale,
  options: Intl.NumberFormatOptions = {},
): Intl.NumberFormat {
  // Polish groups only from five digits by default; the design wants "1 234,50 €".
  return new Intl.NumberFormat(intlTag(locale), { useGrouping: 'always', ...options });
}

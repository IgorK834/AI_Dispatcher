import { PLAN_TIME_ZONE } from './types';

const SHORT_LOCALES = { en: 'en-GB', pl: 'pl-PL' } as const;

/** "Mon 17:30" in the plan zone: a weekday and the clock, for axes and narrow places. */
export function formatClock(iso: string, locale: 'en' | 'pl'): string {
  const parts = new Intl.DateTimeFormat(SHORT_LOCALES[locale], {
    timeZone: PLAN_TIME_ZONE,
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(iso));
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? '';
  return `${pick('weekday')} ${pick('hour')}:${pick('minute')}`;
}

/** Minutes between two ISO instants. */
export const minutesBetween = (from: string, to: string) =>
  Math.round((new Date(to).getTime() - new Date(from).getTime()) / 60000);

/** "+€12.00" or "−€12.00"; zero has no sign. */
export function signed(value: number, text: string): string {
  if (value === 0) return text;
  return `${value > 0 ? '+' : '−'}${text}`;
}

/** "PLAN-1a2b3c4d": the short reference of a plan. */
export const planRef = (id: string) => `PLAN-${id.replaceAll('-', '').slice(0, 8)}`;

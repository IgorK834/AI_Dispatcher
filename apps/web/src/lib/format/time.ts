import { intlTag, type AppLocale } from './locale';

/** 805 minutes is "13 h 25 min"; whole hours drop the minutes part only below one hour. */
export function formatDuration(totalMinutes: number): string {
  const rounded = Math.max(0, Math.round(totalMinutes));
  const hours = Math.floor(rounded / 60);
  const minutes = rounded % 60;
  return hours === 0 ? `${minutes} min` : `${hours} h ${minutes} min`;
}

function zoneAbbreviation(date: Date, timeZone: string): string {
  // English short names give "CET"/"CEST"; the Polish locale would give "GMT+1".
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone, timeZoneName: 'short' }).formatToParts(
    date,
  );
  return parts.find((part) => part.type === 'timeZoneName')?.value ?? timeZone;
}

/** A stop time in the stop's own time zone with the zone shown: "Mon 16 Nov, 06:00 CET". */
export function formatDateTime(iso: string, timeZone: string, locale: AppLocale): string {
  const date = new Date(iso);
  const parts = new Intl.DateTimeFormat(intlTag(locale), {
    timeZone,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date);
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? '';
  return `${pick('weekday')} ${pick('day')} ${pick('month')}, ${pick('hour')}:${pick('minute')} ${zoneAbbreviation(date, timeZone)}`;
}
